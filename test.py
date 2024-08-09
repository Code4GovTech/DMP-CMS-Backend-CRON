import httpx, logging, os, unittest,random
from app import app
from db import SupabaseInterface  
from app import define_issue_description_update, define_pr_update, define_issue_update, async_session
from query import PostgresORM
from sqlalchemy.orm import aliased
from sqlalchemy.future import select
from models import *

# Suppress asyncio debug messages
logging.getLogger('asyncio').setLevel(logging.CRITICAL)

# Optionally, you can also suppress other debug messages if needed
logging.basicConfig(level=logging.CRITICAL)

class CustomTestResult(unittest.TextTestResult):
    def addSuccess(self, test):
        super().addSuccess(test)
        print(f"{test._testMethodName} - passed")

class CustomTestRunner(unittest.TextTestRunner):
    resultclass = CustomTestResult

    def run(self, test):
        result = super().run(test)
        if result.wasSuccessful():
            print("All Testcases Passed")
        return result
    
class TestDMPUpdates(unittest.IsolatedAsyncioTestCase):
    
    async def asyncSetUp(self):
        self.app = app
        self.client = self.app.test_client()
        self.db = SupabaseInterface().get_instance()
        self.issue_response = None
        self.comments_response = None
        self.pr_response = None

        # CHANGE BELOW DB CALL WHEN CHANGES MADE IN PostgresORM.get_all_dmp_issues()        
        async with async_session() as session:
            # Alias for the DmpOrg table to use in the JSON_BUILD_OBJECT
            dmp_org_alias = aliased(DmpOrg)

            # Build the query
            query = (
                select(
                    DmpIssue,
                    func.json_build_object(
                        'created_at', dmp_org_alias.created_at,
                        'description', dmp_org_alias.description,
                        'id', dmp_org_alias.id,
                        'link', dmp_org_alias.link,
                        'name', dmp_org_alias.name,
                        'repo_owner', dmp_org_alias.repo_owner
                    ).label('dmp_orgs')
                )
                .outerjoin(dmp_org_alias, DmpIssue.org_id == dmp_org_alias.id)
                .filter(DmpIssue.org_id.isnot(None))
                .order_by(DmpIssue.id)
            )
            
            # Execute the query and fetch results
            result = await session.execute(query)
            rows = result.fetchall()
            
            # Convert results to dictionaries
            data = []
            for row in rows:
                issue_dict = row._asdict()  # Convert row to dict
                dmp_orgs = issue_dict.pop('dmp_orgs')  # Extract JSON object from row
                issue_dict['dmp_orgs'] = dmp_orgs
                issue_dict.update(issue_dict['DmpIssue'].to_dict())
                # Add JSON object back to dict
                del issue_dict['DmpIssue']
                data.append(issue_dict)
                
        dmp_tickets = data
        if not dmp_tickets:
            self.skipTest("No dmp_tickets found")
            
        dmp = dmp_tickets[random.randint(0,len(dmp_tickets)-1)]
        self.dmp_id = dmp['id']
        self.issue_number = dmp['issue_number']
        self.repo = dmp['repo']
        self.owner = dmp['dmp_orgs']['repo_owner']

        GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')  # Ensure this is correctly set in your environment
        self.description_url = f"https://api.github.com/repos/{self.owner}/{self.repo}/issues/{self.issue_number}"
        self.comments_url = f"https://api.github.com/repos/{self.owner}/{self.repo}/issues/{self.issue_number}/comments?page=1"
        self.pr_url = f"https://api.github.com/repos/{self.owner}/{self.repo}/pulls?state=all"

        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "X-GitHub-Api-Version": "2022-11-28"
        }

        async with httpx.AsyncClient() as client:
            # Test GitHub API call for issue description
            issue_response = await client.get(self.description_url, headers=headers)
            if issue_response.status_code == 200:
                self.issue_response = issue_response.json()
            else:
                self.skipTest(f"GitHub API call failed with status code {issue_response.status_code}")

            # Test GitHub API call for comments
            comments_response = await client.get(self.comments_url, headers=headers)
            if comments_response.status_code == 200:
                self.comments_response = comments_response.json()
            else:
                self.skipTest(f"GitHub comments API call failed with status code {comments_response.status_code}")

            # Test GitHub API call for PRs
            pr_response = await client.get(self.pr_url, headers=headers)
            if pr_response.status_code == 200:
                self.pr_response = pr_response.json()
            else:
                self.skipTest(f"GitHub PRs API call failed with status code {pr_response.status_code}")

    async def test_github_api_call(self):
        self.assertIsNotNone(self.issue_response, "No issue response was fetched")
        self.assertEqual(self.issue_response['state'], 'open', "Issue state should be open")

    async def test_github_comments_call(self):
        self.assertIsNotNone(self.comments_response, "No comments response was fetched")
        self.assertIsInstance(self.comments_response, list, "The comments response should be a list")
        self.assertTrue(len(self.comments_response) >= 0, "The comments list should not be negative")

    async def test_github_prs_call(self):
        self.assertIsNotNone(self.pr_response, "No PRs response was fetched")
        self.assertIsInstance(self.pr_response, list, "The PRs response should be a list")
        self.assertTrue(len(self.pr_response) >= 0, "The PRs list should not be negative")

    def test_define_issue_description_update(self):
        self.assertIsNotNone(self.issue_response, "No issue response was fetched")
        issue_update = define_issue_description_update(self.issue_response)
        self.assertIsInstance(issue_update, dict, "The result should be a dictionary")
        self.assertTrue(len(issue_update) > 0, "The result should not be an empty dictionary")

    def test_define_pr_update(self):
        self.assertIsNotNone(self.pr_response, "No pr response was fetched")
        if self.pr_response==[]:
            self.skipTest(f"No data for PR")
        pr_response = define_pr_update(self.pr_response[0], self.dmp_id)
        self.assertIsInstance(pr_response, dict, "The result should be a dictionary")
        self.assertTrue(len(pr_response) > 0, "The result should not be an empty dictionary")

    def test_define_issue_update(self):
        self.assertIsNotNone(self.comments_response, "No pr response was fetched")
        issue_response = define_issue_update(self.comments_response[0], self.dmp_id)
        self.assertIsInstance(issue_response, dict, "The result should be a dictionary")
        self.assertTrue(len(issue_response) > 0, "The result should not be an empty dictionary")
                
    def test_get_dmp_issues(self):
        # Fetch dmp issues from the database
        dmp_tickets = self.db.get_dmp_issues()
        self.assertTrue(len(dmp_tickets) > 0, "No dmp_tickets found")

        # Call the function to test
        issue_response = define_issue_update(self.comments_response[0],self.dmp_id)
   
        # Call the function to test
        issue_response = define_issue_update(self.comments_response[0],self.dmp_id)
        
        # Check if the function returns a non-empty result
        self.assertIsInstance(issue_response, dict, "The result should be a dictionary")
        self.assertTrue(len(issue_response) > 0, "The result should not be an empty dictionary")
   
        # Check if the function returns a non-empty result
        self.assertIsInstance(issue_response, dict, "The result should be a dictionary")
        self.assertTrue(len(issue_response) > 0, "The result should not be an empty dictionary")
    
    def test_get_dmp_issues(self):
        # Fetch dmp issues from the database
        dmp_tickets = self.db.get_dmp_issues()
        self.assertTrue(len(dmp_tickets) > 0, "No dmp_tickets found")
   
   
if __name__ == '__main__':
    unittest.main(testRunner=CustomTestRunner())
