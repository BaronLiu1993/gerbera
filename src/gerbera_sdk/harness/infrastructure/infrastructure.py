from dataclasses import dataclass, field
from pydo import Client
import os
import uuid
import time

# Repository Layer that connects to whatever API layer and talks to it
@dataclass
class Infrastructure:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))  
    client: Client = Client(token=os.getenv("DIGITALOCEAN_TOKEN"))

    @staticmethod
    def create_payload(name: str, region: str, size: str):
        return {
            "name": name,
            "region": region,
            "size": size,
            "image": "ubuntu-22-04-x64",
            "backups": False,
            "ipv6": True
        }

    def create_vm(self, name: str, region: str, size: str):
        client = self.client.get_client
        droplet_payload = self.create_payload(name, region, size)
        response = client.droplets.create(body=droplet_payload)
        droplet_id = response["droplet"]["id"]
        completed = False

        while not completed:
            current_status = client.droplets.get(droplet_id=droplet_id)
            if current_status == "active":
                completed = True
            time.sleep(3)
        
        return True

        
    