from dataclasses import dataclass

from gerbera_sdk.models.hardware.hardware_plan import ResolvedBoard
from gerbera_sdk.models.runtime.boards.board_runtime import BoardRuntime


@dataclass(frozen=True)
class FirmwareVerifier:
    board_runtime: BoardRuntime

    def verify(self) -> None:
        for board in self.board_runtime.hardware_plan.boards:
            self.verify_board(board)

    def verify_board(self, board: ResolvedBoard) -> None:
        transport = self.board_runtime.transport_factory.create(board)
        try:
            transport.connect()
            BoardRuntime.verify_contract(board, transport)
        finally:
            transport.close()
