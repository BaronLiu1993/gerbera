from gerbera_harness.agent.model.database import Database

class ReviewProcess:
    database: Database

    def complete_goal(self):
        pass

    def select_rows(self, query: str):
        with self.database.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SET LOCAL statement_timeout = '5s'")
                cur.execute(query)

                return cur.fetchmany()
    
    def average_rows(self, query: str):
        pass

    def minimum_rows(self, query: str):
        pass

    def maxiumum_rows(self, query: str):
        pass



        
