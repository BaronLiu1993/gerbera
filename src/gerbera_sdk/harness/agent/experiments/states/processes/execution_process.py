from dataclasses import dataclass

@dataclass
class ExecutionProcess:
    action_set: list

    # We Need to Verify Whether or Not the Action Sets are All Valid
    def _verify_valid_execute_action_group(self, action_group):
        for action in action_group:
            if action.action_type != "execute":
                return False
        return True
        


    def parse_fields(self):
        for step in self.action_set:
            # Check if Valid Action Group
            if step.action_type == ""
            self._verify_execute_action_group


            
        
        
