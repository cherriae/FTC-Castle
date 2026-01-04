
import requests

def test_team_events_endpoint():
    team = 24306
    season = 2025
    url = f"https://api.ftcscout.org/rest/v1/teams/{team}/events/{season}"
    print(f"Testing {url}")
    
    try:
        resp = requests.get(url)
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"Found {len(data)} events")
            print(data)
        else:
            print(resp.text)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_team_events_endpoint()
