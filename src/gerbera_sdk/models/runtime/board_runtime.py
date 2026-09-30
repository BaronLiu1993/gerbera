from dataclasses import dataclass, field
import secrets
import threading
import time

from gerbera_sdk.firmware.firmware_schema import (
    GERBERA_CHECK,
    GERBERA_HANDSHAKE,
    GERBERA_HANDSHAKE_TARGET,
    GERBERA_HEARTBEAT,
    GERBERA_PROTOCOL_VERSION,
    GERBERA_START,
    GERBERA_STOP,
)
from gerbera_sdk.models.hardware.hardware_plan import HardwarePlan, ResolvedBoard
from gerbera_sdk.models.runtime.serial_protocol import (
    SerialMessage,
    SerialMessageCodec,
)
from gerbera_sdk.models.runtime.board_transport import (
    BoardTransport,
    BoardTransportFactory,
)

HANDSHAKE_CHALLENGE_BYTES = 16
HANDSHAKE_FIELDS = frozenset({"protocol", "board", "digest", "challenge"})
CHECK_PASS_FIELDS = frozenset({"status", "session"})
CHECK_FAIL_FIELDS = frozenset({"status", "error", "session"})
START_FIELDS = frozenset({"state", "session"})
THREAD_JOIN_TIMEOUT_SECONDS = 2.0


@dataclass(frozen=True)
class ExpectedSerialMessage:
    message_type: str
    target: str
    fields: frozenset[str]


@dataclass
class BoardSession:
    transport: BoardTransport
    session_id: str
    heartbeat_interval_ms: int
    heartbeat_stop: threading.Event = field(default_factory=threading.Event)
    heartbeat_thread: threading.Thread = field(init=False)
    next_sequence: int = 1

    def __post_init__(self) -> None:
        self.heartbeat_thread = threading.Thread(
            target=self.heartbeat_loop,
            daemon=False,
            name=f"board-heartbeat-{self.session_id}",
        )

    def heartbeat_loop(self) -> None:
        interval_seconds = self.heartbeat_interval_ms / 1000
        deadline = time.monotonic() + interval_seconds
        while not self.heartbeat_stop.wait(
            max(0.0, deadline - time.monotonic())
        ):
            self.send_heartbeat()
            deadline += interval_seconds

    def send_heartbeat(self) -> None:
        self.transport.write(
            SerialMessageCodec.encode(
                SerialMessage(
                    message_type=GERBERA_HEARTBEAT,
                    target=GERBERA_HANDSHAKE_TARGET,
                    fields={
                        "session": self.session_id,
                        "sequence": str(self.next_sequence),
                    },
                )
            )
        )
        self.next_sequence += 1

    def stop_heartbeat(self) -> None:
        self.heartbeat_stop.set()
        self.heartbeat_thread.join(timeout=THREAD_JOIN_TIMEOUT_SECONDS)
        if self.heartbeat_thread.is_alive():
            raise RuntimeError("Board heartbeat thread did not stop")


@dataclass
class BoardRuntime:
    hardware_plan: HardwarePlan
    transport_pool: dict[str, BoardTransport] = field(default_factory=dict)
    sessions: dict[str, BoardSession] = field(default_factory=dict)
    transport_factory: BoardTransportFactory = field(
        default_factory=BoardTransportFactory
    )
    lock: threading.RLock = field(
        default_factory=threading.RLock,
        init=False,
        repr=False,
    )

    def start(self) -> None:
        try:
            for board in self.hardware_plan.boards:
                self.start_board(board)
        except Exception as exc:
            cleanup_error: Exception | None = None
            try:
                self.close()
            except Exception as close_exc:
                cleanup_error = close_exc
            message = "Could not start board runtime"
            if cleanup_error is not None:
                message += f"; cleanup also failed: {cleanup_error}"
            raise RuntimeError(message) from exc

    def start_board(self, board: ResolvedBoard) -> None:
        with self.lock:
            if board.microcontroller_id in self.sessions:
                raise RuntimeError(
                    "Board session is already registered: "
                    f"{board.microcontroller_id}"
                )

        transport = self.transport_factory.create(board)
        session_id = ""
        transport.connect()
        try:
            session_id = self.verify_contract(board, transport)
            self.verify_components(board, transport, session_id)
            self.start_firmware(transport, session_id)
            self.send_first_heartbeat(transport, session_id)
            session = BoardSession(
                transport=transport,
                session_id=session_id,
                heartbeat_interval_ms=(
                    board.watchdog.heartbeat_interval_ms
                ),
            )
            session.heartbeat_thread.start()
        except Exception:
            if session_id:
                self.attempt_stop(transport, session_id)
            transport.close()
            raise

        with self.lock:
            self.sessions[board.microcontroller_id] = session
            self.transport_pool[board.microcontroller_id] = transport

    @staticmethod
    def verify_contract(
        board: ResolvedBoard,
        connection: BoardTransport,
    ) -> str:
        challenge = secrets.token_hex(HANDSHAKE_CHALLENGE_BYTES)
        connection.write(
            SerialMessageCodec.encode(
                SerialMessage(
                    message_type=GERBERA_HANDSHAKE,
                    target=GERBERA_HANDSHAKE_TARGET,
                    fields={"challenge": challenge},
                )
            )
        )
        response = BoardRuntime.read_response(
            connection,
            f"Board handshake timed out: {board.microcontroller_id}",
        )
        BoardRuntime.require_message(
            response,
            ExpectedSerialMessage(
                GERBERA_HANDSHAKE,
                GERBERA_HANDSHAKE_TARGET,
                HANDSHAKE_FIELDS,
            ),
        )
        expected_fields = {
            "protocol": str(GERBERA_PROTOCOL_VERSION),
            "board": board.microcontroller_id,
            "digest": board.contract_digest,
            "challenge": challenge,
        }
        if dict(response.fields) != expected_fields:
            raise RuntimeError(
                f"Board contract does not match: {board.microcontroller_id}"
            )
        return challenge

    @staticmethod
    def verify_components(
        board: ResolvedBoard,
        connection: BoardTransport,
        session_id: str,
    ) -> None:
        for component in board.connections:
            component_key = (
                f"{board.microcontroller_id}.{component.name}"
            )
            connection.write(
                SerialMessageCodec.encode(
                    SerialMessage(
                        message_type=GERBERA_CHECK,
                        target=component_key,
                        fields={"session": session_id},
                    )
                )
            )
            response = BoardRuntime.read_response(
                connection,
                f"Component check timed out: {component_key}",
            )
            expected = {"status": "pass", "session": session_id}
            if (
                response.message_type == GERBERA_CHECK
                and response.target == component_key
                and response.fields.keys() == CHECK_PASS_FIELDS
                and dict(response.fields) == expected
            ):
                continue
            failure = {
                "status": "fail",
                "error": "component_check_failed",
                "session": session_id,
            }
            if (
                response.message_type == GERBERA_CHECK
                and response.target == component_key
                and response.fields.keys() == CHECK_FAIL_FIELDS
                and dict(response.fields) == failure
            ):
                raise RuntimeError(f"Component check failed: {component_key}")
            raise RuntimeError(
                f"Board returned an invalid component check: {component_key}"
            )

    @staticmethod
    def start_firmware(
        connection: BoardTransport,
        session_id: str,
    ) -> None:
        connection.write(
            SerialMessageCodec.encode(
                SerialMessage(
                    message_type=GERBERA_START,
                    target=GERBERA_HANDSHAKE_TARGET,
                    fields={"session": session_id},
                )
            )
        )
        response = BoardRuntime.read_response(
            connection,
            "Board start timed out",
        )
        BoardRuntime.require_message(
            response,
            ExpectedSerialMessage(
                GERBERA_START,
                GERBERA_HANDSHAKE_TARGET,
                START_FIELDS,
            ),
        )
        expected = {"state": "READY", "session": session_id}
        if dict(response.fields) != expected:
            raise RuntimeError("Board did not enter READY")

    @staticmethod
    def send_first_heartbeat(
        connection: BoardTransport,
        session_id: str,
    ) -> None:
        connection.write(
            SerialMessageCodec.encode(
                SerialMessage(
                    message_type=GERBERA_HEARTBEAT,
                    target=GERBERA_HANDSHAKE_TARGET,
                    fields={"session": session_id, "sequence": "0"},
                )
            )
        )

    @staticmethod
    def read_response(
        connection: BoardTransport,
        timeout_message: str,
    ) -> SerialMessage:
        raw_response = connection.readline()
        if not raw_response:
            raise TimeoutError(timeout_message)
        return SerialMessageCodec.decode(raw_response)

    @staticmethod
    def require_message(
        response: SerialMessage,
        expected: ExpectedSerialMessage,
    ) -> None:
        if response.message_type != expected.message_type:
            raise RuntimeError("Board returned an invalid message type")
        if response.target != expected.target:
            raise RuntimeError("Board returned an invalid message target")
        if response.fields.keys() != expected.fields:
            raise RuntimeError("Board returned invalid message fields")

    def get_transport(
        self,
        microcontroller_id: str,
    ) -> BoardTransport:
        with self.lock:
            connection = self.transport_pool.get(microcontroller_id)
        if connection is None:
            raise RuntimeError(
                f"Microcontroller is not connected: {microcontroller_id}"
            )
        return connection

    def reconnect_board(self, microcontroller_id: str) -> None:
        self.close_board(microcontroller_id)
        try:
            board = self.hardware_plan.boards_by_id[microcontroller_id]
        except KeyError as exc:
            raise RuntimeError(
                f"Unknown microcontroller: {microcontroller_id}"
            ) from exc
        self.start_board(board)

    def close_board(self, microcontroller_id: str) -> None:
        with self.lock:
            session = self.sessions.pop(microcontroller_id, None)
            self.transport_pool.pop(microcontroller_id, None)
        if session is None:
            return
        try:
            session.stop_heartbeat()
        finally:
            session.transport.close()

    @staticmethod
    def attempt_stop(
        connection: BoardTransport,
        session_id: str,
    ) -> None:
        try:
            BoardRuntime.send_stop(connection, session_id)
        except Exception:
            return

    @staticmethod
    def send_stop(connection: BoardTransport, session_id: str) -> None:
        connection.write(
            SerialMessageCodec.encode(
                SerialMessage(
                    message_type=GERBERA_STOP,
                    target=GERBERA_HANDSHAKE_TARGET,
                    fields={"session": session_id},
                )
            )
        )

    def close(self) -> None:
        with self.lock:
            sessions = list(self.sessions.items())

        first_error: Exception | None = None
        for microcontroller_id, session in sessions:
            try:
                session.stop_heartbeat()
                self.send_stop(session.transport, session.session_id)
            except Exception as exc:
                if first_error is None:
                    first_error = exc
            finally:
                try:
                    session.transport.close()
                except Exception as exc:
                    if first_error is None:
                        first_error = exc
                with self.lock:
                    self.sessions.pop(microcontroller_id, None)
                    self.transport_pool.pop(microcontroller_id, None)

        if first_error is not None:
            raise RuntimeError("Could not stop board runtime") from first_error
