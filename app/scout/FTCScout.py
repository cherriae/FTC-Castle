import logging
import os
from datetime import datetime
from functools import lru_cache
from typing import Union
import requests

logger = logging.getLogger(__name__)

class FTCScout:
    def __init__(self):
        self._API_URI: str = "https://api.ftcscout.org/rest/v1"
        self._GRAPHQL_URI: str = "https://api.ftcscout.org/graphql"

        self.headers = {
            "accept": "application/json"
        }

        self.timeout = 5 

    @lru_cache(maxsize=100)
    def get_all_events(self, season: int, start: str = None, end: str = None, limit: int = None, 
                       region: str = None, event_type: str = "All", has_matches: bool = None, 
                       search_text: str = None):
        """Get all events using GraphQL
        
        Args:
            season: Season year (e.g., 2025 for Decode) (REQUIRED)
            start: Start date in YYYY-MM-DD format (optional)
            end: End date in YYYY-MM-DD format (optional)
            limit: Maximum number of results (optional)
            region: Region option (optional)
            event_type: Event type (optional, default is "All")
            has_matches: Filter by whether event has matches (optional)
            search_text: Text to search for (optional)
        """
        try:
            # Build GraphQL query
            query = """
            query EventsSearch($season: Int!, $region: RegionOption, $type: EventTypeOption, $hasMatches: Boolean, 
                             $start: Date, $end: Date, $limit: Int, $searchText: String) {
                eventsSearch(season: $season, region: $region, type: $type, hasMatches: $hasMatches,
                           start: $start, end: $end, limit: $limit, searchText: $searchText) {
                    code
                    name
                    start
                    end
                    season
                    type
                    remote
                    location {
                        city
                        state
                        country
                    }
                    regionCode
                }
            }
            """
            
            variables = {
                "season": season
            }
            if start:
                variables['start'] = start
            if end:
                variables['end'] = end
            if limit:
                variables['limit'] = limit
            if region:
                variables['region'] = region
            if event_type:
                variables['type'] = event_type
            if has_matches is not None:
                variables['hasMatches'] = has_matches
            if search_text:
                variables['searchText'] = search_text
            
            response = requests.post(
                self._GRAPHQL_URI,
                headers={
                    "accept": "application/json",
                    "content-type": "application/json"
                },
                json={"query": query, "variables": variables},
                timeout=self.timeout
            )

            if response.status_code == 200:
                data = response.json()
                if 'errors' in data:
                    logger.error(f"GraphQL errors: {data['errors']}")
                    return None
                events = data.get('data', {}).get('eventsSearch', None)
                
                # Sort events by start date
                if events and isinstance(events, list):
                    try:
                        events = sorted(events, key=lambda x: x.get('start', ''))
                    except Exception as e:
                        logger.warning(f"Could not sort events by start date: {e}")
                
                return events
            else:
                logger.error(f"API returned status {response.status_code}: {response.text[:200]}")
                return None
        except Exception as e:
            logger.error(f"Error fetching events from FTCScout: {e}")
            return None

    @lru_cache(maxsize=100)
    def get_all_matches(self, season: int, code: str) -> Union[dict, None]:
        """Get all matches in a certain event
        
        Args:
            season: Season year
            code: Event code
        """
        try:
            response = requests.get(
                f"{self._API_URI}/events/{season}/{code}/matches",
                headers=self.headers,
                timeout=self.timeout
            )

            return response.json() if response.status_code == 200 else None
        except Exception as e:
            logger.error(f"Error fetching matches from FTCScout: {e}")
            return None

    @lru_cache(maxsize=100)
    def get_team(self, team: int) -> Union[dict, None]:
        """Get team information
        
        Args:
            team: Team number
        """
        try:
            response = requests.get(
                f"{self._API_URI}/teams/{team}",
                headers=self.headers,
                timeout=self.timeout
            )

            return response.json() if response.status_code == 200 else None
        except Exception as e:
            logger.error(f"Error fetching team from FTCScout: {e}")
            return None

    @lru_cache(maxsize=100)
    def get_team_events(self, team: int, season: int) -> Union[list, None]:
        """Get events for a team in a season
        
        Args:
            team: Team number
            season: Season year
        """
        try:
            response = requests.get(
                f"{self._API_URI}/teams/{team}/events/{season}",
                headers=self.headers,
                timeout=self.timeout
            )

            return response.json() if response.status_code == 200 else None
        except Exception as e:
            logger.error(f"Error fetching team events from FTCScout: {e}")
            return None

    @lru_cache(maxsize=100)
    def get_event_details(self, season: int, code: str) -> Union[dict, None]:
        """Get event details
        
        Args:
            season: Season year
            code: Event code
        """
        try:
            response = requests.get(
                f"{self._API_URI}/events/{season}/{code}",
                headers=self.headers,
                timeout=self.timeout
            )

            return response.json() if response.status_code == 200 else None
        except Exception as e:
            logger.error(f"Error fetching event details from FTCScout: {e}")
            return None

    @lru_cache(maxsize=100)
    def get_quick_stats(self, team: int, season: int = None, region: str = None) -> Union[dict, None]:
        """Get quick stats for a team
        
        Args:
            team: Team number
            season: Season year (optional)
            region: Region option (optional)
        """
        try:
            params = {}
            if season:
                params['season'] = season
            if region:
                params['region'] = region
                
            response = requests.get(
                f"{self._API_URI}/teams/{team}/quick-stats",
                headers=self.headers,
                params=params,
                timeout=self.timeout
            )

            return response.json() if response.status_code == 200 else None
        except Exception as e:
            logger.error(f"Error fetching quick stats from FTCScout: {e}")
            return None

    @lru_cache(maxsize=100)
    def get_event_rankings(self, season: int, code: str) -> Union[list, None]:
        """Get event rankings using GraphQL
        
        Args:
            season: Season year
            code: Event code
        """
        try:
            # Construct query with dynamic fragment based on season
            # Note: This assumes the API naming convention follows the season year
            fragment_name = f"TeamEventStats{season}"
            
            # Use alias for matchesPlayed to normalize output
            query = """
            query EventTeams($season: Int!, $code: String!) {
                eventByCode(season: $season, code: $code) {
                    teams {
                        teamNumber
                        stats {
                            ... on """ + fragment_name + """ {
                                rank
                                wins
                                losses
                                ties
                                matchesPlayed: qualMatchesPlayed
                            }
                        }
                    }
                }
            }
            """
            
            variables = {
                "season": season,
                "code": code
            }
            
            response = requests.post(
                self._GRAPHQL_URI,
                headers={
                    "accept": "application/json",
                    "content-type": "application/json"
                },
                json={"query": query, "variables": variables},
                timeout=self.timeout
            )

            if response.status_code == 200:
                data = response.json()
                if 'errors' in data:
                    logger.error(f"GraphQL errors: {data['errors']}")
                    return None
                    
                teams_data = data.get('data', {}).get('eventByCode', {}).get('teams', [])
                
                # Transform to expected format
                rankings = []
                for t in teams_data:
                    stats = t.get('stats')
                    if stats:
                        rankings.append({
                            'teamNumber': t.get('teamNumber'),
                            'rank': stats.get('rank'),
                            'matchesPlayed': stats.get('matchesPlayed'),
                            'wins': stats.get('wins'),
                            'losses': stats.get('losses'),
                            'ties': stats.get('ties')
                        })
                
                # Sort by rank
                rankings.sort(key=lambda x: x.get('rank', 999))
                return rankings
            else:
                logger.error(f"API returned status {response.status_code}: {response.text[:200]}")
                return None
        except Exception as e:
            logger.error(f"Error fetching rankings from FTCScout: {e}")
            return None

