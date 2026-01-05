#TODO

from __future__ import annotations

import json
from datetime import datetime, timezone

from bson import ObjectId, json_util
from flask import (Blueprint, current_app, flash, jsonify, redirect,
                   render_template, request, url_for)
from flask_login import current_user, login_required

import logging
from app.scout.scouting_utils import ScoutingManager
from app.utils import handle_route_errors

from .FTCScout import FTCScout

scouting_bp = Blueprint("scouting", __name__)
scouting_manager = None
ftc = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@scouting_bp.record
def on_blueprint_init(state):
    global scouting_manager, ftc
    app = state.app
    
    # Create ScoutingManager with the singleton connection
    scouting_manager = ScoutingManager(app.config["MONGO_URI"])
    
    # Initialize FTCScout
    global ftc
    ftc = FTCScout()
    
    # Store in app context for proper cleanup
    if not hasattr(app, 'db_managers'):
        app.db_managers = {}
    app.db_managers['scouting'] = scouting_manager


@scouting_bp.route("/scouting/add", methods=["GET", "POST"])
@login_required
# @limiter.limit("15 per minute")
@handle_route_errors
def add():
    if request.method != "POST":
        # Get current events only
        current_date = datetime.now()
        season = current_date.year
        if current_date.month < 9:
            season -= 1
            
        events_list = ftc.get_all_events(season) or []
        events = {}
        for e in events_list:
            # Map FTCScout event to expected format
            # FTCScout: code, name, start
            events[e['name']] = {
                'key': e['code'],
                'start_date': e['start']
            }
        
        return render_template("scouting/add.html", 
                            events=events,
                            event_matches={})  # Empty dict

    data = request.get_json() if request.is_json else request.form.to_dict()

    if "auto_path" in data:
        try:
            if isinstance(data["auto_path"], str):
                if data["auto_path"].strip(): 
                    data["auto_path"] = json.loads(data["auto_path"])
                else:
                    data["auto_path"] = [] 
        except json.JSONDecodeError:
            flash("Invalid path coordinates format", "error")
            return redirect(url_for("scouting.home"))

    success, message = scouting_manager.add_scouting_data(data, current_user.get_id())
    current_app.logger.info(f"Tried to add scouting data ({success}) {data} for user {current_user.username if current_user.is_authenticated else 'Anonymous'} - {message}")
    current_app.logger.info(f"Scouting.add Form Details {request.form} - {message}")

    if success:
        flash("Team data added successfully", "success")
    else:
        flash(f"Error adding data: {message}", "error")

    return redirect(url_for("scouting.home"))


@scouting_bp.route("/scouting/list")
@scouting_bp.route("/scouting")
# @limiter.limit("30 per minute")
@login_required
def home():
    try:
        team_data = scouting_manager.get_all_scouting_data(
            current_user.teamNumber, 
            current_user.get_id()
        )

        # Get the user's team if they have one
        team = None
        if current_user.teamNumber:
            team_query = {"team_number": current_user.teamNumber}
            if team_doc := scouting_manager.db.teams.find_one(team_query):
                from app.models import Team
                team = Team.create_from_db(team_doc)
        current_app.logger.info(f"Successfully fetched team data for user {current_user.username if current_user.is_authenticated else 'Anonymous'}")
        return render_template("scouting/list.html", team_data=team_data, team=team)
    except Exception as e:
        current_app.logger.error(f"Error fetching scouting data: {str(e)}", exc_info=True)
        flash("Unable to fetch scouting data. Please try again later.", "error")
        return render_template("scouting/list.html", team_data=[])


@scouting_bp.route("/scouting/edit/<string:id>", methods=["GET", "POST"])
# @limiter.limit("15 per minute")
@login_required
def edit(id):
    try:
        team_data = scouting_manager.get_team_data(id, current_user.get_id())

        if not team_data:
            flash("Team data not found", "error")
            return redirect(url_for("scouting.home"))

        # Check if the current user is on the same team as the scouter
        current_team = current_user.teamNumber
        scouter_team = team_data.scouter_team
        
        # Allow access only if user is the original scouter or on the same team
        if current_user.get_id() != team_data.scouter_id and (not current_team or not scouter_team or str(current_team) != str(scouter_team)):
            flash("Access denied: You can only edit scouting data from your own team", "error")
            return redirect(url_for("scouting.home"))

        if request.method == "POST":
            data = request.form.to_dict()
            current_app.logger.info(f"Scouting.edit Form Details {request.form}")
            # Add edit tracking - record who made the edit
            data['last_edited_by'] = current_user.get_id()
            data['last_edited_at'] = datetime.now().isoformat()
            
            # Convert the drawing coordinates from string to JSON if present
            if "auto_path_coords" in data and isinstance(data["auto_path_coords"], str):
                try:
                    json.loads(data["auto_path_coords"])  # Validate JSON
                except json.JSONDecodeError:
                    flash("Invalid path coordinates format", "error")
                    return render_template("scouting/edit.html", team_data=team_data)
            
            if scouting_manager.update_team_data(id, data, current_user.get_id()):
                flash("Data updated successfully", "success")
                current_app.logger.info(f"Successfully updated scouting data {data} for user {current_user.username if current_user.is_authenticated else 'Anonymous'}")
                return redirect(url_for("scouting.home"))
            
            current_app.logger.info(f"Failed to update scouting data {data} for user {current_user.username if current_user.is_authenticated else 'Anonymous'}")
            flash("Unable to update data", "error")

        return render_template("scouting/edit.html", team_data=team_data)
    except Exception as e:
        current_app.logger.error(f"Error in edit_scouting_data: {str(e)}", exc_info=True)
        flash("An error occurred while processing your request", "error")
        return redirect(url_for("scouting.home"))


@scouting_bp.route("/scouting/delete/<string:id>")
# @limiter.limit("10 per minute")
@login_required
def delete(id):
    try:
        # Get information about the record before deleting for better error messages
        team_data = scouting_manager.get_team_data(id, current_user.get_id())
        if not team_data:
            flash("Record not found", "error")
            return redirect(url_for("scouting.home"))

        # Attempt to delete
        if scouting_manager.delete_team_data(id, current_user.get_id()):
            current_app.logger.info(f"Successfully deleted scouting data {id} for user {current_user.username if current_user.is_authenticated else 'Anonymous'}")
            flash("Record deleted successfully", "success")
        elif team_data.scouter_id == current_user.get_id():
            flash("Error deleting your record. Please try again.", "error")
        elif current_user.teamNumber and team_data.scouter_team == current_user.teamNumber:
            # Check if user is team admin using existing database connection
            team_query = {"team_number": current_user.teamNumber}
            if team_doc := scouting_manager.db.teams.find_one(team_query):
                from app.models import Team
                team = Team.create_from_db(team_doc)
                
                if team.is_admin(current_user.get_id()):
                    # Try to delete again with admin override
                    if scouting_manager.delete_team_data(id, current_user.get_id(), admin_override=True):
                        current_app.logger.info(f"Successfully deleted scouting data {id} for user {current_user.username if current_user.is_authenticated else 'Anonymous'} (admin)")
                        flash("Record deleted successfully (admin)", "success")
                    else:
                        current_app.logger.info(f"Failed to delete scouting data {id} for user {current_user.username if current_user.is_authenticated else 'Anonymous'} (admin)")
                        flash("Error deleting team member's record. Please try again.", "error")
                else:
                    current_app.logger.info(f"Permission denied: You must be a team admin to delete other members' records {id} for user {current_user.username if current_user.is_authenticated else 'Anonymous'}")
                    flash("Permission denied: You must be a team admin to delete other members' records", "error")
            else:
                current_app.logger.info(f"Permission denied: Team not found {id} for user {current_user.username if current_user.is_authenticated else 'Anonymous'}")
                flash("Permission denied: Team not found", "error")
        else:
            current_app.logger.info(f"Permission denied: You can only delete records from your own team {id} for user {current_user.username if current_user.is_authenticated else 'Anonymous'}")
            flash("Permission denied: You can only delete records from your own team", "error")
    except Exception as e:
        current_app.logger.error(f"Delete error: {str(e)}", exc_info=True)
        flash("An internal error has occurred.", "error")
    return redirect(url_for("scouting.home"))


@scouting_bp.route("/lighthouse")
# @limiter.limit("30 per minute")
@login_required
def lighthouse():
    current_app.logger.info(f"Successfully fetched lighthouse for user {current_user.username if current_user.is_authenticated else 'Anonymous'}")
    return render_template("lighthouse.html")

@scouting_bp.route("/lighthouse/auton")
# @limiter.limit("30 per minute")
@login_required
def auton():
    current_app.logger.info(f"Successfully fetched lighthouse/auton for user {current_user.username if current_user.is_authenticated else 'Anonymous'}")
    return render_template("lighthouse/auton.html")


#TODO
@scouting_bp.route("/api/compare")
# @limiter.limit("30 per minute")
@login_required
def compare_teams():
    try:
        teams = []
        for i in range(1, 4):
            if team_num := request.args.get(f'team{i}'):
                teams.append(int(team_num))

        if len(teams) < 2:
            return jsonify({"error": "At least 2 teams are required"}), 400

        teams_data = {}
        for team_num in teams:
            try:
                pipeline = [
                    {"$match": {"team_number": team_num}},
                    {"$lookup": {
                        "from": "users",
                        "localField": "scouter_id",
                        "foreignField": "_id",
                        "as": "scouter"
                    }},
                    {"$unwind": "$scouter"},
                    {"$match": {
                        "$or": [
                            {"scouter.teamNumber": current_user.teamNumber} if current_user.teamNumber else {"scouter._id": ObjectId(current_user.get_id())},
                            {"scouter._id": ObjectId(current_user.get_id())}
                        ]
                    }},
                    {"$group": {
                        "_id": "$team_number",
                        "matches_played": {"$sum": 1},
                        "avg_auto_purple_classified": {"$avg": {"$cond": [{"$gt": ["$auto_purple_classified", 0]}, "$auto_purple_classified", None]}},
                        "avg_auto_green_classified": {"$avg": {"$cond": [{"$gt": ["$auto_green_classified", 0]}, "$auto_green_classified", None]}},
                        "avg_auto_purple_overflow": {"$avg": {"$cond": [{"$gt": ["$auto_purple_overflow", 0]}, "$auto_purple_overflow", None]}},
                        "avg_auto_green_overflow": {"$avg": {"$cond": [{"$gt": ["$auto_green_overflow", 0]}, "$auto_green_overflow", None]}},
                        "avg_teleop_purple_classified": {"$avg": {"$cond": [{"$gt": ["$teleop_purple_classified", 0]}, "$teleop_purple_classified", None]}},
                        "avg_teleop_green_classified": {"$avg": {"$cond": [{"$gt": ["$teleop_green_classified", 0]}, "$teleop_green_classified", None]}},
                        "avg_teleop_purple_overflow": {"$avg": {"$cond": [{"$gt": ["$teleop_purple_overflow", 0]}, "$teleop_purple_overflow", None]}},
                        "avg_teleop_green_overflow": {"$avg": {"$cond": [{"$gt": ["$teleop_green_overflow", 0]}, "$teleop_green_overflow", None]}},
                        # Only count successful climbs in the rate
                        "climb_success_rate": {"$avg": {"$cond": ["$climb_success", 1, 0]}},
                        "auto_paths": {"$push": {
                            "path": "$auto_path",
                            "notes": "$auto_notes",
                            "match_number": "$match_number"
                        }},
                        "robot_disabled_list": {"$push": "$robot_disabled"},
                        "preferred_climb_type": {"$last": "$climb_type"},
                        "matches": {"$push": "$$ROOT"}
                    }},
                    {"$match": {"matches_played": {"$gt": 0}}}
                ]

                if stats := list(
                    scouting_manager.db.team_data.aggregate(pipeline)
                ):
                    normalized_stats = {
                        "auto_scoring": (
                            (stats[0]["avg_auto_purple_classified"] or 0) + 
                            (stats[0]["avg_auto_green_classified"] or 0) +
                            (stats[0]["avg_auto_purple_overflow"] or 0) +
                            (stats[0]["avg_auto_green_overflow"] or 0)
                        ) / 20,
                        "teleop_scoring": (
                            (stats[0]["avg_teleop_purple_classified"] or 0) + 
                            (stats[0]["avg_teleop_green_classified"] or 0) +
                            (stats[0]["avg_teleop_purple_overflow"] or 0) +
                            (stats[0]["avg_teleop_green_overflow"] or 0)
                        ) / 20,
                        "climb_rating": stats[0]["climb_success_rate"],
                    }

                    # Get team info from FTCScout
                    team_info = ftc.get_team(team_num) or {}

                    teams_data[str(team_num)] = {
                        "team_number": team_num,
                        "nickname": team_info.get("name", "Unknown"),
                        "city": team_info.get("city"),
                        "state_prov": team_info.get("state"),
                        "country": team_info.get("country"),
                        "stats": stats[0],
                        "normalized_stats": normalized_stats,
                        "matches": stats[0]["matches"]
                    }

            except Exception as team_error:
                current_app.logger.error(f"Error processing team {team_num}: {str(team_error)}", exc_info=True)

        if not teams_data:
            return jsonify({"error": "No data available for the selected teams"}), 404

        current_app.logger.info(f"Successfully fetched team data {teams_data} for user {current_user.username if current_user.is_authenticated else 'Anonymous'}")
        return json_util.dumps(teams_data)

    except Exception as e:
        current_app.logger.error(f"Error in compare_teams: {str(e)}", exc_info=True)
        return jsonify({"error": "An error occurred while comparing teams"}), 500

@scouting_bp.route("/api/search")
@login_required
# @limiter.limit("30 per minute")
def search_teams():
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify([])

    try:
        # Handle both numeric and text searches
        team = None
        if query.isdigit():
            team = ftc.get_team(int(query))
        
        if not team:
            return jsonify([])

        # Get team number from the response
        team_number = team.get("number")
        
        # Fetch scouting data from our database
        pipeline = [
            {"$match": {"team_number": team_number}},
            {"$lookup": {
                "from": "users",
                "localField": "scouter_id",
                "foreignField": "_id",
                "as": "scouter"
            }},
            {"$unwind": {"path": "$scouter"}},
            # Add team access filter
            {"$match": {
                "$or": [
                    {"scouter.teamNumber": current_user.teamNumber} if current_user.teamNumber else {"scouter._id": ObjectId(current_user.get_id())},
                    {"scouter._id": ObjectId(current_user.get_id())}
                ]
            }},
            {"$sort": {"event_code": 1, "match_number": 1}},
            {
                "$project": {
                    "_id": {"$toString": "$_id"},  # Convert ObjectId to string
                    "event_code": 1,
                    "match_number": 1,
                    "auto_purple_classified": {"$ifNull": ["$auto_purple_classified", 0]},
                    "auto_green_classified": {"$ifNull": ["$auto_green_classified", 0]},
                    "auto_purple_overflow": {"$ifNull": ["$auto_purple_overflow", 0]},
                    "auto_green_overflow": {"$ifNull": ["$auto_green_overflow", 0]},
                    "teleop_purple_classified": {"$ifNull": ["$teleop_purple_classified", 0]},
                    "teleop_green_classified": {"$ifNull": ["$teleop_green_classified", 0]},
                    "teleop_purple_overflow": {"$ifNull": ["$teleop_purple_overflow", 0]},
                    "teleop_green_overflow": {"$ifNull": ["$teleop_green_overflow", 0]},
                    "pattern_completed": 1,
                    "climb_type": 1,
                    "climb_success": 1,
                    "auto_path": 1,
                    "auto_notes": 1,
                    "notes": 1,
                    "scouter_name": "$scouter.username",
                    "scouter_id": {"$toString": "$scouter._id"} 
                }
            }
        ]

        scouting_data = list(scouting_manager.db.team_data.aggregate(pipeline))

        # Format response
        response_data = [{
            "team_number": team_number,
            "nickname": team.get("name"),
            "school_name": team.get("schoolName"),
            "city": team.get("city"),
            "state_prov": team.get("state"),
            "country": team.get("country"),
            "scouting_data": scouting_data,
            "has_team_page": bool(scouting_data)  # True if we have any scouting data
        }]

        # Use json_util.dumps to handle MongoDB types
        current_app.logger.info(f"Successfully fetched team data {response_data} for user {current_user.username if current_user.is_authenticated else 'Anonymous'}")
        return json_util.dumps(response_data), 200, {'Content-Type': 'application/json'}

    except Exception as e:
        current_app.logger.error(f"Error in search_teams: {str(e)}", exc_info=True)
        return jsonify({"error": "Failed to fetch team data due to an internal error."}), 500

@scouting_bp.route("/leaderboard")
# @limiter.limit("30 per minute")
def leaderboard():
    try:
        MIN_MATCHES = 1
        sort_type = request.args.get('sort', 'total')
        selected_event = request.args.get('event', 'all')
        
        # Get available events from scouting data
        # Filter by team access: only show events from user's team or user himself
        events_pipeline = [
            # Join with users collection to get scouter information
            {
                "$lookup": {
                    "from": "users",
                    "localField": "scouter_id",
                    "foreignField": "_id",
                    "as": "scouter"
                }
            },
            {"$unwind": "$scouter"},
            # Filter by team access
            {"$match": {
                "$or": [
                    {"scouter.teamNumber": current_user.teamNumber} if current_user.teamNumber else {"scouter._id": ObjectId(current_user.get_id())},
                    {"scouter._id": ObjectId(current_user.get_id())}
                ]
            }},
            # Group by event code to get unique events
            {"$group": {
                "_id": "$event_code",
                "event_name": {"$first": "$event_name"},
                "count": {"$sum": 1}
            }},
            {"$sort": {"_id": 1}}
        ]
        
        events = list(scouting_manager.db.team_data.aggregate(events_pipeline))
        
        # Main pipeline for team data
        pipeline = [
            # Join with users collection to get scouter information
            {
                "$lookup": {
                    "from": "users",
                    "localField": "scouter_id",
                    "foreignField": "_id",
                    "as": "scouter"
                }
            },
            {"$unwind": "$scouter"},
            # Filter by team access
            {"$match": {
                "$or": [
                    {"scouter.teamNumber": current_user.teamNumber} if current_user.teamNumber else {"scouter._id": ObjectId(current_user.get_id())},
                    {"scouter._id": ObjectId(current_user.get_id())}
                ]
            }}
        ]
        
        # Filter by selected event if not 'all'
        if selected_event != 'all':
            pipeline.append({"$match": {"event_code": selected_event}})
        
        # Continue with the existing aggregation
        pipeline.extend([
            {"$group": {
                "_id": "$team_number",
                "matches_played": {"$sum": 1},

                "auto_purple_classified": {"$avg": {"$ifNull": ["$auto_purple_classified", 0]}},
                "auto_green_classified": {"$avg": {"$ifNull": ["$auto_green_classified", 0]}},
                "auto_purple_overflow": {"$avg": {"$ifNull": ["$auto_purple_overflow", 0]}},
                "auto_green_overflow": {"$avg": {"$ifNull": ["$auto_green_overflow", 0]}},
                # Teleop
                "teleop_purple_classified": {"$avg": {"$ifNull": ["$teleop_purple_classified", 0]}},
                "teleop_green_classified": {"$avg": {"$ifNull": ["$teleop_green_classified", 0]}},
                "teleop_purple_overflow": {"$avg": {"$ifNull": ["$teleop_purple_overflow", 0]}},
                "teleop_green_overflow": {"$avg": {"$ifNull": ["$teleop_green_overflow", 0]}},
                
                # Robot Disabled
                "robot_disabled_list": {"$push": "$robot_disabled"},

                # Climb stats
                "climb_attempts": {"$sum": 1},
                "climb_successes": {
                    "$sum": {"$cond": [{"$eq": ["$climb_success", True]}, 1, 0]}
                },
                "park_attempts": {
                    "$sum": {"$cond": [{"$eq": ["$climb_type", "park"]}, 1, 0]}
                },
                "park_successes": {
                    "$sum": {
                        "$cond": [
                            {"$and": [
                                {"$eq": ["$climb_type", "park"]},
                                {"$eq": ["$climb_success", True]}
                            ]},
                            1,
                            0
                        ]
                    }
                },
                "complete_park_attempts": {
                    "$sum": {"$cond": [{"$eq": ["$climb_type", "complete park"]}, 1, 0]}
                },
                "complete_park_successes": {
                    "$sum": {
                        "$cond": [
                            {"$and": [
                                {"$eq": ["$climb_type", "complete park"]},
                                {"$eq": ["$climb_success", True]}
                            ]},
                            1,
                            0
                        ]
                    }
                },
                "stacked_park_attempts": {
                    "$sum": {"$cond": [{"$eq": ["$climb_type", "stacked park"]}, 1, 0]}
                },
                "stacked_park_successes": {
                    "$sum": {
                        "$cond": [
                            {"$and": [
                                {"$eq": ["$climb_type", "stacked park"]},
                                {"$eq": ["$climb_success", True]}
                            ]},
                            1,
                            0
                        ]
                    }
                }
            }},
            {"$match": {"matches_played": {"$gte": MIN_MATCHES}}},
            {"$project": {
                "team_number": "$_id",
                "matches_played": 1,
                "auto_stats": {
                    "purple_classified": "$auto_purple_classified",
                    "green_classified": "$auto_green_classified",
                    "purple_overflow": "$auto_purple_overflow",
                    "green_overflow": "$auto_green_overflow"
                },
                "teleop_stats": {
                    "purple_classified": "$teleop_purple_classified",
                    "green_classified": "$teleop_green_classified",
                    "purple_overflow": "$teleop_purple_overflow",
                    "green_overflow": "$teleop_green_overflow"
                },
                # Calculate totals for each category
                "total_score": {
                    "$add": [
                        "$auto_purple_classified", "$auto_green_classified", 
                        "$auto_purple_overflow", "$auto_green_overflow",
                        "$teleop_purple_classified", "$teleop_green_classified", 
                        "$teleop_purple_overflow", "$teleop_green_overflow"
                    ]
                },
                "total_auto": {
                    "$add": [
                        "$auto_purple_classified", "$auto_green_classified", 
                        "$auto_purple_overflow", "$auto_green_overflow"
                    ]
                },
                "total_teleop": {
                    "$add": [
                        "$teleop_purple_classified", "$teleop_green_classified", 
                        "$teleop_purple_overflow", "$teleop_green_overflow"
                    ]
                },
                "climb_success_rate": {
                    "$multiply": [
                        {"$cond": [
                            {"$gt": ["$climb_attempts", 0]},
                            {"$divide": ["$climb_successes", "$climb_attempts"]},
                            0
                        ]},
                        100
                    ]
                },
                "park_success_rate": {
                    "$multiply": [
                        {"$cond": [
                            {"$gt": ["$park_attempts", 0]},
                            {"$divide": ["$park_successes", "$park_attempts"]},
                            0
                        ]},
                        100
                    ]
                },
                "complete_park_success_rate": {
                    "$multiply": [
                        {"$cond": [
                            {"$gt": ["$complete_park_attempts", 0]},
                            {"$divide": ["$complete_park_successes", "$complete_park_attempts"]},
                            0
                        ]},
                        100
                    ]
                },
                "stacked_park_success_rate": {
                    "$multiply": [
                        {"$cond": [
                            {"$gt": ["$stacked_park_attempts", 0]},
                            {"$divide": ["$stacked_park_successes", "$stacked_park_attempts"]},
                            0
                        ]},
                        100
                    ]
                },
                "robot_disabled_list": "$robot_disabled_list"
            }}
        ])

        # Add sorting based on selected type
        sort_field = {
            'total': 'total_score',
            'auto': 'total_auto',
            'teleop': 'total_teleop',
            'climb': 'climb_success_rate',
            'park': 'park_success_rate',
            'complete_park': 'complete_park_success_rate',
            'stacked_park': 'stacked_park_success_rate'
        }.get(sort_type, 'total_score')

        pipeline.append({"$sort": {sort_field: -1}})

        teams = list(scouting_manager.db.team_data.aggregate(pipeline))
        
        return render_template("scouting/leaderboard.html", teams=teams, current_sort=sort_type, 
                              events=events, selected_event=selected_event)
    except Exception as e:
        current_app.logger.error(f"Error in leaderboard: {str(e)}", exc_info=True)
        return render_template("scouting/leaderboard.html", teams=[], current_sort='total', 
                              events=[], selected_event='all')

@scouting_bp.route("/scouter-leaderboard")
# @limiter.limit("30 per minute")
@login_required
def scouter_leaderboard():
    try:
        sort_by = request.args.get('sort', 'match_count')
        selected_event = request.args.get('event', 'all')
        selected_team = request.args.get('team', 'all')
        
        # Get list of events for filtering
        events_pipeline = [
            {"$group": {"_id": "$event_code"}},
            {"$sort": {"_id": 1}}
        ]
        events = [evt["_id"] for evt in scouting_manager.db.team_data.aggregate(events_pipeline)]
        
        # Build pipeline to count scouting entries by user
        pipeline = [
            # Join with users to get scouter information
            {
                "$lookup": {
                    "from": "users",
                    "localField": "scouter_id",
                    "foreignField": "_id",
                    "as": "scouter"
                }
            },
            {"$unwind": "$scouter"},
        ]
        
        # Apply event filter if specified
        if selected_event != 'all':
            pipeline.append({"$match": {"event_code": selected_event}})
            
        # Apply team filter if specified
        if selected_team != 'all' and selected_team.isdigit():
            pipeline.append({"$match": {"scouter.teamNumber": int(selected_team)}})
            
        # Group by scouter and count
        pipeline.extend([
            {
                "$group": {
                    "_id": "$scouter._id",
                    "username": {"$first": "$scouter.username"},
                    "teamNumber": {"$first": "$scouter.teamNumber"},
                    "match_count": {"$sum": 1},
                    "unique_teams": {"$addToSet": "$team_number"},
                }
            },
            {
                "$project": {
                    "username": 1,
                    "teamNumber": 1,
                    "match_count": 1,
                    "unique_teams_count": {"$size": "$unique_teams"},
                }
            }
        ])
        
        # Sort by selected field
        sort_field = {
            'match_count': 'match_count',
            'unique_teams': 'unique_teams_count',
        }.get(sort_by, 'match_count')
        
        pipeline.append({"$sort": {sort_field: -1}})
        
        # Execute query
        scouters = list(scouting_manager.db.team_data.aggregate(pipeline))
        
        # Get list of all teams for filtering
        teams_pipeline = [
            {"$lookup": {
                "from": "users",
                "localField": "scouter_id",
                "foreignField": "_id",
                "as": "scouter"
            }},
            {"$unwind": "$scouter"},
            {"$match": {"scouter.teamNumber": {"$exists": True, "$ne": None}}},
            {"$group": {"_id": "$scouter.teamNumber"}},
            {"$sort": {"_id": 1}}
        ]
        teams = [team["_id"] for team in scouting_manager.db.team_data.aggregate(teams_pipeline)]
        
        current_app.logger.info(f"Successfully fetched scouter leaderboard {scouters} for user {current_user.username if current_user.is_authenticated else 'Anonymous'}")
        return render_template(
            "scouting/scouter-leaderboard.html", 
            scouters=scouters, 
            current_sort=sort_by,
            events=events, 
            selected_event=selected_event,
            teams=teams,
            selected_team=selected_team
        )
    except Exception as e:
        current_app.logger.error(f"Error fetching scouter leaderboard: {str(e)}", exc_info=True)
        return render_template(
            "scouting/scouter-leaderboard.html", 
            scouters=[], 
            current_sort='match_count',
            events=[], 
            selected_event='all',
            teams=[],
            selected_team='all'
        )


# TODO
@scouting_bp.route("/api/ftc/events")
@login_required
# @limiter.limit("30 per minute")
def get_ftc_events():
    try:
        current_date = datetime.now()
        season = current_date.year
        if current_date.month < 9:
            season -= 1
            
        events_list = ftc.get_all_events(season) or []
        events = {}
        for e in events_list:
            events[e['name']] = {
                'key': e['code'],
                'start_date': e['start']
            }
            
        current_app.logger.info(f"Successfully fetched FTC events {events} for user {current_user.username if current_user.is_authenticated else 'Anonymous'}")
        return jsonify(events)
    except Exception as e:
        current_app.logger.error(f"Error getting FTC events: {e}")
        return jsonify({"error": "Failed to fetch events"}), 500

#TODO
@scouting_bp.route("/api/ftc/matches/<event_code>")
@login_required
# @limiter.limit("30 per minute")
def get_ftc_matches(event_code):
    try:
        current_date = datetime.now()
        season = current_date.year
        if current_date.month < 9:
            season -= 1
            
        matches = ftc.get_all_matches(season, event_code) or []
        
        # Sort matches by ID to ensure correct order
        matches.sort(key=lambda x: x.get('id', 0))
        
        formatted_matches = {}
        
        # Counters for match numbering
        qual_counter = 1
        semi_counter = 1
        final_counter = 1

        for m in matches:
            # Map comp_level
            level = m.get('tournamentLevel', 'Quals')
            if level == 'Quals' or level == 'QUALIFICATION':
                comp_level = 'qm'
                prefix = 'Qual'
                match_num = qual_counter
                qual_counter += 1
            elif level == 'Semis' or level == 'SEMIFINAL':
                comp_level = 'sf'
                prefix = 'Semifinal'
                match_num = semi_counter
                semi_counter += 1
            elif level == 'Finals' or level == 'FINAL':
                comp_level = 'f'
                prefix = 'Final'
                match_num = final_counter
                final_counter += 1
            elif level == 'DoubleElim':
                comp_level = 'de'
                prefix = 'Match'
                match_num = m.get('series', 0)
            else:
                comp_level = 'qm'
                prefix = 'Qual'
                match_num = qual_counter
                qual_counter += 1
                
            match_key = f"{prefix} {match_num}"
            
            # Map teams
            red = []
            blue = []
            
            # Handle different potential team structures
            if 'teams' in m:
                for t in m['teams']:
                    team_num = str(t.get('teamNumber'))
                    if t.get('alliance') == 'Red':
                        red.append(team_num)
                    elif t.get('alliance') == 'Blue':
                        blue.append(team_num)
            elif 'red' in m and 'blue' in m:
                # Assuming simple dict with team numbers
                if isinstance(m['red'], list):
                    red = [str(t) for t in m['red']]
                if isinstance(m['blue'], list):
                    blue = [str(t) for t in m['blue']]

            formatted_matches[match_key] = {
                'red': red,
                'blue': blue,
                'comp_level': comp_level,
                'match_number': match_num,
                'set_number': m.get('series', None)
            }
            
        current_app.logger.info(f"Successfully fetched FTC matches {formatted_matches} for user {current_user.username if current_user.is_authenticated else 'Anonymous'}")
        return jsonify(formatted_matches)
    except Exception as e:
        current_app.logger.error(f"Error getting FTC matches: {e}")
        return jsonify({"error": "Failed to fetch matches"}), 500

#TODO
@scouting_bp.route("/scouting/live-match-status", methods=["GET"])
@login_required
# @limiter.limit("30 per minute")
def live_match_status():
    """Route for the live team schedule modal"""
    team_number = request.args.get('team')
    event_code = request.args.get('event')
    
    # Default to empty context data
    context = {
        'team_number': team_number,
        'event_code': event_code
    }
    current_app.logger.info(f"Successfully fetched live match status {context} for user {current_user.username if current_user.is_authenticated else 'Anonymous'}")
    return render_template("scouting/live-match-status.html", **context)

#TODO
@scouting_bp.route("/api/ftc/team-status")
@login_required
# @limiter.limit("30 per minute")
def get_team_status():
    """Get team status at an event including ranking and matches"""
    team_number = request.args.get('team')
    event_code = request.args.get('event')
    
    if not team_number:
        return jsonify({"error": "Team number is required"}), 400
    
    try:
        current_date = datetime.now()
        season = current_date.year
        if current_date.month < 9:
            season -= 1

        if not event_code:
             # Try to find the most recent event for the team
             team_events = ftc.get_team_events(team_number, season)
             
             if team_events:
                 # Fetch details for each event to get start dates
                 events_with_dates = []
                 for e in team_events:
                     code = e.get('eventCode')
                     if code:
                         details = ftc.get_event_details(season, code)
                         if details:
                             events_with_dates.append(details)
                 
                 if events_with_dates:
                     # Sort by start date
                     events_with_dates.sort(key=lambda x: x.get('start', ''))
                     
                     # Find the last event that has started (start <= today)
                     today_str = current_date.strftime('%Y-%m-%d')
                     selected_event = None
                     
                     # Iterate backwards to find the most recent started event
                     for e in reversed(events_with_dates):
                         if e.get('start', '9999-99-99') <= today_str:
                             selected_event = e
                             break
                     
                     # If no event has started yet, pick the first upcoming one
                     if not selected_event and events_with_dates:
                         selected_event = events_with_dates[0]
                         
                     if selected_event:
                         event_code = selected_event.get('code')
             
             if not event_code:
                 return jsonify({"error": "No events found for this team"}), 404

        # Get all matches for event
        all_matches = ftc.get_all_matches(season, event_code) or []
        
        # Sort matches by ID to ensure correct order
        all_matches.sort(key=lambda x: x.get('id', 0))
        
        # Counters for match numbering
        qual_counter = 1
        semi_counter = 1
        final_counter = 1
        
        # Filter for team and format
        previous_matches = []
        upcoming_matches = []
        
        for m in all_matches:
            # Determine match number and prefix
            level = m.get('tournamentLevel', 'Quals')
            if level == 'Quals' or level == 'QUALIFICATION':
                prefix = 'Qual'
                match_num = qual_counter
                qual_counter += 1
            elif level == 'Semis' or level == 'SEMIFINAL':
                prefix = 'Semifinal'
                match_num = semi_counter
                semi_counter += 1
            elif level == 'Finals' or level == 'FINAL':
                prefix = 'Final'
                match_num = final_counter
                final_counter += 1
            elif level == 'DoubleElim':
                prefix = 'Playoffs'
                match_num = m.get('series', 0)
            else:
                prefix = 'Qual'
                match_num = qual_counter
                qual_counter += 1
            
            match_name = f"{prefix} {match_num}"

            in_match = False
            alliance = 'unknown'
            
            if 'teams' in m:
                for t in m['teams']:
                    if str(t.get('teamNumber')) == str(team_number):
                        in_match = True
                        alliance = t.get('alliance', '').lower()
                        break
            elif 'red' in m and 'blue' in m:
                 if str(team_number) in [str(x) for x in m['red']]:
                     in_match = True
                     alliance = 'red'
                 elif str(team_number) in [str(x) for x in m['blue']]:
                     in_match = True
                     alliance = 'blue'

            if in_match:
                # Determine if played
                has_score = False
                red_score = 0
                blue_score = 0
                
                # Check for scores in various potential formats
                if m.get('scores'):
                    has_score = True
                    # Handle nested score objects (FTCScout format)
                    scores = m['scores']
                    if isinstance(scores.get('red'), dict):
                        red_score = scores['red'].get('totalPoints', 0)
                    else:
                        red_score = scores.get('red', 0)
                        
                    if isinstance(scores.get('blue'), dict):
                        blue_score = scores['blue'].get('totalPoints', 0)
                    else:
                        blue_score = scores.get('blue', 0)
                elif m.get('redScore') is not None and m.get('blueScore') is not None:
                    has_score = True
                    red_score = m.get('redScore')
                    blue_score = m.get('blueScore')
                
                # Parse time
                match_time = 0
                # Try multiple time fields in order of preference
                time_str = m.get('actualStartTime') or m.get('scheduledStartTime') or m.get('postResultTime')
                
                if time_str:
                    try:
                        # Handle ISO format
                        match_time = datetime.fromisoformat(time_str.replace('Z', '+00:00')).timestamp()
                    except:
                        pass
                elif m.get('time'): 
                    match_time = m.get('time')

                match_data = {
                    'match_name': match_name,
                    'time': match_time,
                    'alliance': alliance,
                    'score': {
                        'red': red_score,
                        'blue': blue_score
                    } if has_score else None
                }
                
                if has_score:
                    previous_matches.append(match_data)
                else:
                    upcoming_matches.append(match_data)
        
        # Get team ranking
        rankings = ftc.get_event_rankings(season, event_code) or []
        team_rank = None
        for r in rankings:
            if str(r.get('teamNumber')) == str(team_number):
                team_rank = r
                break
        
        status = None
        if team_rank:
            status = {
                "qual": {
                    "ranking": {
                        "rank": team_rank.get('rank'),
                        "matches_played": team_rank.get('matchesPlayed'),
                        "record": {
                            "wins": team_rank.get('wins'),
                            "losses": team_rank.get('losses'),
                            "ties": team_rank.get('ties')
                        }
                    }
                }
            }

        current_app.logger.info(f"Successfully fetched team status for user {current_user.username if current_user.is_authenticated else 'Anonymous'}")

        return jsonify({
            "status": status,
            "matches": {
                "previous": previous_matches,
                "upcoming": upcoming_matches
            },
            "event": {
                "key": event_code,
                "name": event_code # Placeholder
            }
        })
    except Exception as e:
        logger.error(f"Error getting team status: {e}")
        return jsonify({"error": "Failed to fetch team status"}), 500

@scouting_bp.route("/api/team_paths")
@login_required
# @limiter.limit("30 per minute")
def get_team_paths():
    team_number = request.args.get('team')
    
    if not team_number:
        return jsonify({"error": "Team number is required"}), 400
    
    try:
        team_number = int(team_number)
        
        # Build pipeline to get paths for the team
        pipeline = [
            {"$match": {"team_number": team_number}},
            {"$lookup": {
                "from": "users",
                "localField": "scouter_id",
                "foreignField": "_id",
                "as": "scouter"
            }},
            {"$unwind": {"path": "$scouter", "preserveNullAndEmptyArrays": True}},
            # Add team access filter
            {"$match": {
                "$or": [
                    {"scouter.teamNumber": current_user.teamNumber} if current_user.teamNumber else {"scouter._id": ObjectId(current_user.get_id())},
                    {"scouter._id": ObjectId(current_user.get_id())}
                ]
            }},
            # Only get matches with auto path data
            {"$match": {"auto_path": {"$exists": True, "$ne": []}}},
            # Sort by most recent matches first
            {"$sort": {"match_number": -1}},
            # Project only the needed fields
            {"$project": {
                "_id": {"$toString": "$_id"},
                "team_number": 1,
                "match_number": 1,
                "event_code": 1,
                "event_name": 1,
                "alliance": 1,
                "auto_path": 1,
                "auto_notes": 1,
                "scouter_name": "$scouter.username",
                "scouter_id": {"$toString": "$scouter._id"}
            }}
        ]
        
        # Get team info from FTCScout
        team_info = ftc.get_team(team_number) or {}
        
        # Get paths from database
        paths = list(scouting_manager.db.team_data.aggregate(pipeline))
        
        # Format response
        response = {
            "team_number": team_number,
            "team_info": {
                "nickname": team_info.get("name", "Unknown"),
                "city": team_info.get("city", ""),
                "state_prov": team_info.get("state", ""),
                "country": team_info.get("country", "")
            },
            "paths": paths
        }
        
        current_app.logger.info(f"Successfully fetched team paths {response} for user {current_user.username if current_user.is_authenticated else 'Anonymous'}")
        return json_util.dumps(response), 200, {'Content-Type': 'application/json'}
        
    except Exception as e:
        current_app.logger.error(f"Error fetching team paths: {str(e)}", exc_info=True)
        return jsonify({"error": "Failed to fetch team path data."}), 500
