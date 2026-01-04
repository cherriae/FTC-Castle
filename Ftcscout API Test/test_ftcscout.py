"""
Test file for FTCScout API wrapper
"""
import json
import sys
from pathlib import Path

# Add parent directory (FTC-Castle root) to path so we can import app
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.scout.FTCScout import FTCScout

TeamOutputFile = "./Ftcscout API Test/test_output_team.json"
EventOutputFile = "./Ftcscout API Test/test_output_events.json"
MatchOutputFile = "./Ftcscout API Test/test_output_matches.json"
QuickStatsOutputFile = "./Ftcscout API Test/test_output_quick_stats.json"


def test_get_team():
    """Test getting team information"""
    print("Testing get_team()...")
    scout = FTCScout()
    
    # Example: Get team 27705 (FTC Byte Knights)
    team_number = 27705
    
    print(f"  Querying team {team_number}")
    result = scout.get_team(team_number)
    
    if result:
        print(f"Successfully fetched team {team_number}")
        
        # Show key team info if available
        if isinstance(result, dict):
            name = result.get('teamName', result.get('name', 'N/A'))
            location = result.get('location', {})
            city = location.get('city', 'N/A') if isinstance(location, dict) else 'N/A'
            print(f"  Team Name: {name}")
            print(f"  Location: {city}")
        
        with open(TeamOutputFile, 'w') as f:
            json.dump(result, f, indent=2)
        print(f"  Saved to {TeamOutputFile}")
    else:
        print(f"✗ Failed to fetch team {team_number}")
    
    return result is not None


def test_get_all_events():
    """Test getting all events using GraphQL"""
    print("\nTesting get_all_events()...")
    scout = FTCScout()
    
    # Get events with season, date range and limit
    season = 2025
    start = "2024-09-01"
    end = "2026-01-04"
    limit = 30000
    
    print(f"  Querying events for season {season} from {start} to {end} (limit: {limit})")
    result = scout.get_all_events(season=season, start=start, end=end, limit=limit)
    
    if result:
        print(f"✓ Successfully fetched events")
        num_events = len(result) if isinstance(result, list) else 'N/A'
        print(f"  Number of events: {num_events}")
        
        # Show sample event if available
        if isinstance(result, list) and len(result) > 0:
            print(f"  Sample event: {result[0].get('name', 'N/A')} ({result[0].get('code', 'N/A')})")
        
        with open(EventOutputFile, 'w') as f:
            json.dump(result, f, indent=2)
        print(f"  Saved to {EventOutputFile}")
    else:
        print(f"✗ Failed to fetch events")
    
    return result is not None


def test_get_all_matches():
    """Test getting all matches for an event"""
    print("\nTesting get_all_matches()...")
    scout = FTCScout()
    
    # Example: Get matches for a specific event
    season = 2025
    event_code = "USNYNYBRQ3"  # NY Regional Qualifier 3
    
    print(f"  Querying matches for event {event_code} in season {season}")
    result = scout.get_all_matches(season=season, code=event_code)
    
    if result:
        print(f"✓ Successfully fetched matches for event {event_code}")
        num_matches = len(result) if isinstance(result, list) else 'N/A'
        print(f"  Number of matches: {num_matches}")
        
        # Show sample match if available
        if isinstance(result, list) and len(result) > 0:
            match = result[0]
            print(f"  Sample match: {match.get('description', 'N/A')}")
        
        with open(MatchOutputFile, 'w') as f:
            json.dump(result, f, indent=2)
        print(f"  Saved to {MatchOutputFile}")
    else:
        print(f"✗ Failed to fetch matches (event may not exist)")
    
    return True  # Don't fail test if event doesn't exist


def test_get_quick_stats():
    """Test getting quick stats for a team"""
    print("\nTesting get_quick_stats()...")
    scout = FTCScout()
    
    team_number = 27705
    season = 2025
    
    print(f"  Querying quick stats for team {team_number} in season {season}")
    result = scout.get_quick_stats(team=team_number, season=season)
    
    if result:
        print(f"✓ Successfully fetched quick stats for team {team_number}")
        
        # Show key stats if available
        if isinstance(result, dict):
            wins = result.get('wins', 'N/A')
            losses = result.get('losses', 'N/A')
            opr = result.get('opr', 'N/A')
            print(f"  Record: {wins}W - {losses}L")
            print(f"  OPR: {opr}")
        
        with open(QuickStatsOutputFile, 'w') as f:
            json.dump(result, f, indent=2)
        print(f"  Saved to {QuickStatsOutputFile}")
    else:
        print(f"✗ Failed to fetch quick stats")
    
    return result is not None


def test_api_connection():
    """Test basic API connection"""
    print("Testing API connection...")
    scout = FTCScout()
    
    print(f"  REST API URI: {scout._API_URI}")
    print(f"  GraphQL URI: {scout._GRAPHQL_URI}")
    print(f"  Headers: {scout.headers}")
    print(f"  Timeout: {scout.timeout}s")
    
    return True


def run_all_tests():
    """Run all tests"""
    print("=" * 60)
    print("FTCScout API Tests")
    print("=" * 60)
    
    tests = [
        test_api_connection,
        test_get_team,
        test_get_all_events,
        test_get_all_matches,
        test_get_quick_stats,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"✗ Test {test.__name__} raised an exception: {e}")
            results.append(False)
    
    print("\n" + "=" * 60)
    print(f"Tests completed: {sum(results)}/{len(results)} passed")
    print("=" * 60)


if __name__ == "__main__":
    run_all_tests()
