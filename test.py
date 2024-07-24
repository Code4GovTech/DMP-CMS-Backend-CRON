import httpx,logging,os,unittest
from app import app
from db import SupabaseInterface  
from app import define_issue_description_update ,define_pr_update,define_issue_update 


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
    
class TestDMPUpdates(unittest.IsolatedAsyncioTestCase):
    
    async def asyncSetUp(self):
        self.app = app
        self.client = self.app.test_client()
        self.db = SupabaseInterface().get_instance()
        self.issue_response = None
        self.comments_response = None
        self.pr_response = None

        # Fetch dmp issues from the database
        dmp_tickets = self.db.get_dmp_issues()
        if not dmp_tickets:
            self.skipTest("No dmp_tickets found")

        # Use the first dmp ticket to form the URL
        dmp = dmp_tickets[0]
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
        # Check if the GitHub API call was successful and set the response
        self.assertIsNotNone(self.issue_response, "No issue response was fetched")
        self.assertEqual(self.issue_response['state'], 'open', "Issue state should be open")

    async def test_github_comments_call(self):
        # Check if the GitHub comments API call was successful and set the response
        self.assertIsNotNone(self.comments_response, "No comments response was fetched")
        self.assertIsInstance(self.comments_response, list, "The comments response should be a list")
        self.assertTrue(len(self.comments_response) >= 0, "The comments list should not be negative")

    async def test_github_prs_call(self):
        # Check if the GitHub PRs API call was successful and set the response
        self.assertIsNotNone(self.pr_response, "No PRs response was fetched")
        self.assertIsInstance(self.pr_response, list, "The PRs response should be a list")
        self.assertTrue(len(self.pr_response) >= 0, "The PRs list should not be negative")

    def test_define_issue_description_update(self):
        # Ensure the response was set
        self.assertIsNotNone(self.issue_response, "No issue response was fetched")

        # Call the function to test
        issue_update = define_issue_description_update(self.issue_response)
        
        # Check if the function returns a non-empty result
        self.assertIsInstance(issue_update, dict, "The result should be a dictionary")
        self.assertTrue(len(issue_update) > 0, "The result should not be an empty dictionary")
        
    def test_define_pr_update(self):
        # Ensure the response was set
        self.assertIsNotNone(self.pr_response, "No pr response was fetched")

        # Call the function to test
        pr_response = define_pr_update(self.pr_response[0],self.dmp_id)
        
        # Check if the function returns a non-empty result
        self.assertIsInstance(pr_response, dict, "The result should be a dictionary")
        self.assertTrue(len(pr_response) > 0, "The result should not be an empty dictionary")
        
    def test_define_issue_update(self):
        # Ensure the response was set
        self.assertIsNotNone(self.comments_response, "No pr response was fetched")

        # Call the function to test
        issue_response = define_issue_update(self.comments_response[0],self.dmp_id)
        
        # Check if the function returns a non-empty result
        self.assertIsInstance(issue_response, dict, "The result should be a dictionary")
        self.assertTrue(len(issue_response) > 0, "The result should not be an empty dictionary")
        
    def test_get_dmp_issues(self):
        # Fetch dmp issues from the database
        dmp_tickets = self.db.get_dmp_issues()
        self.assertTrue(len(dmp_tickets) > 0, "No dmp_tickets found")
   
   
if __name__ == '__main__':
    unittest.main(testRunner=CustomTestRunner())
