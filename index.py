import os
import requests
import mlbstatsapi
from itertools import groupby
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.options("/{path:path}")
def options_handler():
    return {"ok": True}

@app.get("/api")
def read_root():
    return {"Python": "on Vercel"}

# get nba data
sportsdata_url = os.getenv("SPORTSDATA_URL")
sportsdata_apikey = os.getenv("SPORTSDATA_APIKEY")
@app.get("/api/NBA/schedules")
def get_schedules(response: Response):
    response.headers["Cache-Control"] = "public, s-maxage=31536000"
    try:
        season = datetime.now().year + 1
        url = f'{sportsdata_url}/SchedulesBasic/{season}'
        headers = {
            "Ocp-Apim-Subscription-Key": sportsdata_apikey
        }
        result = requests.get(url, headers=headers).json()
        
        games = []
        for game in result:
            filtered_game = {
                "gameId": game.get('GameID'),
                "gameDate": game.get('Day'),
                "gameStatus": game.get('Status'),
                "gameLabel": game.get('gameLabel') or None,
                "homeTeam_name": game.get('HomeTeam'),
                "homeTeam_id": game.get('HomeTeamID'),
                "awayTeam_name": game.get('AwayTeam'),
                "awayTeam_id": game.get('AwayTeamID'),
                "homeTeam_score": game.get('HomeTeamScore'),
                "awayTeam_score": game.get('AwayTeamScore'),
                "gameTimeUTC": game.get('DateTimeUTC')
            }
            games.append(filtered_game)
        
        schedules = []
        for date, games_group in groupby(games, key=lambda x:x["gameDate"]):
            schedules.append({
                "date": date,
                "gamesList": list(games_group)
            })

        return {
            "ok": True,
            "error": None,
            "data": schedules
        }

    except Exception as e:
        response.status_code = 500
        return {
            "ok": False,
            "data": None,
            "error": str(e)
        }

@app.get("/api/NBA/standings")
def get_standings(response: Response):
    response.headers["Cache-Control"] = "public, s-maxage=3600"
    try:
        season = datetime.now().year + 1
        urlTeams = f"{sportsdata_url}/teams/{season}"
        urlStandings = f"{sportsdata_url}/Standings/{season}"
        headers = {
            "Ocp-Apim-Subscription-Key": sportsdata_apikey
        }

        teams = requests.get(urlTeams, headers=headers).json()
        result = requests.get(urlStandings, headers=headers).json()

        grouped = { 'east': [], 'west': []}
        for team in result:
            conference = team.get("Conference").lower()
            filtered_team_records = {
                "team_id": team.get('TeamID'),
                "team_name": team.get('Name'),
                "team_city": team.get('City'),
                "team_key": team.get('Key'),
                "wins": team.get('Wins'),
                "losses": team.get('Losses'),
                "winpct": team.get('Percentage'),
                "home": f"{team.get('HomeWins')}-{team.get("HomeLosses")}",
                "road": f"{team.get('AwayWins')}-{team.get("AwayLosses")}",
                "lastTen": f"{team.get('LastTenWins')}-{team.get("LastTenLosses")}",
                "conference": conference,
                "conferenceGamesBack": team.get('GamesBack'),
                "consferenceRecord": f"{team.get('ConferenceWins')}-{team.get("ConferenceLosses")}",
                "currentStreak": team.get('StreakDescription'),
            }
            for t in teams:
                if t.get("TeamID") == team.get("TeamID"):
                    filtered_team_records["team_logo"] = t.get('WikipediaLogoUrl')

            if conference == 'eastern':
                grouped["east"].append(filtered_team_records)
            else:
                grouped["west"].append(filtered_team_records)
            
        grouped["east"] = sorted(grouped["east"], key=lambda x: x["winpct"], reverse=True)
        grouped["west"] = sorted(grouped["west"], key=lambda x: x["winpct"], reverse=True)

        return {
            "ok": True,
            "error":None,
            "data": grouped
        }

    except Exception as e:
        response.status_code = 500
        return {
            "ok": False,
            "data": None,
            "error": str(e)
        }
    
@app.get("/api/NBA/players")
def get_players(response: Response):
    response.headers["Cache-Control"] = "public, s-maxage=84600"
    try:
        season = datetime.now().year + 1
        urlTeams = f"{sportsdata_url}/teams/{season}"
        urlPlayersStats = f"https://api.sportsdata.io/v3/nba/stats/json/PlayerSeasonStats/{season}"
        headers = {
            "Ocp-Apim-Subscription-Key": sportsdata_apikey
        }

        teams = requests.get(urlTeams, headers=headers).json()
        playersStats = requests.get(urlPlayersStats, headers=headers).json()

        players_list = []
        for player in playersStats:
            filtered_player_stats = {
                "player_id": player.get("PlayerID"),
                "player_name": player.get("Name"),
                "player_position": player.get("Position"),
                "team_id": player.get("TeamID"),
                "team_key": player.get("Team"),
                "fantasy_points": player.get("FantasyPoints"),
                "rebounds": player.get("Rebounds"),
                "assists": player.get("Assists"),
                "steals": player.get("Steals"),
                "points": player.get("Points"),
                "per": player.get("PlayerEfficiencyRating"),
                "plus_minus": player.get("PlusMinus"),
            }
            players_list.append(filtered_player_stats)

        def get_weighted_stats(player):
            return (
                0.70 * float(player.get("fantasy_points") or 0) +
                0.20 * float(player.get("per") or 0) +
                0.10 * float(player.get("plus_minus") or 0)
            )
        
        for player in players_list:
            player["player_points"] = get_weighted_stats(player)

        players_list = sorted(players_list, key=lambda x: x['player_points'], reverse=True)[:30]

        for player in players_list:
            for team in teams:
                if team.get("Key") == player.get("team_key"):
                    player["team_name"] = team.get('Name')
                    player["team_city"] = team.get('City')
                    player["team_logo"] = team.get('WikipediaLogoUrl')

        return {
            "ok": True,
            "error": None,
            "data": players_list,
        }
    
    except Exception as e:
        response.status_code = 500
        return {
            "ok": False,
            "data": None,
            "error": str(e)
        }

# get mlb data
@app.get("/api/MLB/schedules")
def get_schedules(response: Response):
    response.headers["Cache-Control"] = "public, s-maxage=31536000"
    try:
        current_date = datetime.now().date()
        current_year_season = datetime.now().year
        next_year_season = current_year_season + 1
    
        mlb = mlbstatsapi.Mlb()
        # current/previous season
        mlb_current_year_season = mlb.get_season(season_id=current_year_season)
        start_date_current = mlb_current_year_season.seasonstartdate
        end_date_current = mlb_current_year_season.seasonenddate

        # upcoming/next season
        mlb_next_year_season = mlb.get_season(season_id=next_year_season)
        start_date_next = mlb_next_year_season.seasonstartdate
        end_date_next = mlb_next_year_season.seasonenddate

        mlb_schedule = None

        # if season ended we want to show the last played games
        if datetime.now().timestamp() >= datetime.strptime(end_date_current, "%Y-%m-%d").timestamp():
            # if current date is > next season start, we get the current date schedules
            if datetime.now().timestamp() >= datetime.strptime(start_date_next, "%Y-%m-%d").timestamp():
                startdate = datetime.now().date() - timedelta(days=10)
                enddate = datetime.now().date() + timedelta(days=10)
                mlb_schedule = mlb.get_schedule(start_date=startdate, end_date=enddate)
            else:
                startdate = datetime.strptime(end_date_current, "%Y-%m-%d").date() - timedelta(days=10)
                mlb_schedule = mlb.get_schedule(start_date=startdate, end_date=end_date_current)
        # season hasn't ended yet, we can normally query using the date today as base   
        elif datetime.now().timestamp() < datetime.strptime(end_date_current, "%Y-%m-%d").timestamp():
            startdate = datetime.now().date() - timedelta(days=10)
            enddate = datetime.now().date() + timedelta(days=10)
            mlb_schedule = mlb.get_schedule(start_date=startdate, end_date=enddate)

        # mlb_teams = mlb.get_teams(sport_id=1)

        schedules = []
        # create an array of games per date
        for date in mlb_schedule.dates:
            game_day = date.date
            game_list = []
            # map the props of the game appended to list
            for game in date.games:
                filtered_game = {
                    "gameId": game.gameguid,
                    "gameDate": game.gamedate,
                    "gamepk": game.gamepk,
                    "gameStatus": game.status.detailedstate,
                    "gameLabel": game.seriesdescription,
                    "homeTeam_name": game.teams.home.team.name,
                    "homeTeam_id": game.teams.home.team.id,
                    "awayTeam_name": game.teams.away.team.name,
                    "awayTeam_id": game.teams.away.team.id,
                    "homeTeam_score": game.teams.home.score,
                    "awayTeam_score": game.teams.away.score,
                    "homeTeam_seriesRecord": game.teams.home.leaguerecord,
                    "awayTeam_seriesRecord": game.teams.away.leaguerecord
                }
                game_list.append(filtered_game)

            schedules.append({
                "date": game_day,
                "gamesList": game_list
            })
        # sort using the date
        schedules.sort(key=lambda x: x["date"])
        
        return {
            "ok": True,
            "error": None,
            "data": schedules
        }
    
    except Exception as e:
        response.status_code = 500
        return {
            "ok": False,
            "data": None,
            "error": str(e)
        }

@app.get('/api/MLB/standings')
def get_standings(response: Response):
    response.headers["Cache-Control"] = "public, s-maxage=3600"
    try:
        current_year = datetime.now().year
        mlb = mlbstatsapi.Mlb()
        # the result is an instance of mlbstatsapi and not an object/dict
        #  so we have to use dot notation to access properties
        mlb_standings = mlb.get_standings(league_id="103,104",season=current_year)

        mlb_teams = mlb.get_teams(sport_id=1)

        mlb_leagues_standings = {
            'american_league': [], 
            'national_league': []
        }

        for team in mlb_teams: 
            league_name = team.league.name
            league_id = team.league.id
            division_name = team.division.name
            division_id = team.division.id

            filtered_team = {
                "team_name": team.name,
                "league_name": league_name,
                "league_id": league_id,
                "division_name": division_name,
                "division_id": division_id,
                "club_name": team.clubname,
                "team_id": team.id,
                "season": team.season,
            }

            for div in mlb_standings:
                if div.division.id == division_id:
                    for t in div.teamrecords:
                        if team.id == t.team.id:
                            filtered_team["league_rank"] = t.leaguerank
                            filtered_team["conferenceGamesBack"] = t.leaguegamesback
                            filtered_team["wins"] = t.leaguerecord["wins"]
                            filtered_team["losses"] = t.leaguerecord["losses"]
                            filtered_team["winpct"] = t.leaguerecord["pct"]
                            filtered_team["ties"] = t.leaguerecord["ties"]
                            filtered_team["currentStreak"] = t.streak.streakcode
                            
                            for lr in t.records["leaguerecords"]:
                                if lr["league"]["id"] == 103:
                                    filtered_team["americanLeagueRecord"] = f"{lr["wins"]}-{lr["losses"]}"
                                if lr["league"]["id"] ==  104:
                                    filtered_team["nationalLeagueRecord"] = f"{lr["wins"]}-{lr["losses"]}"

                            for ovr in t.records["overallrecords"]:
                                if ovr["type"] == "home":
                                    filtered_team["home"] = f"{ovr["wins"]}-{ovr["losses"]}"
                                elif ovr["type"] == "away":
                                    filtered_team["road"] = f"{ovr["wins"]}-{ovr["losses"]}"

                            for sr in t.records["splitrecords"]:
                                if sr["type"] == "lastTen":
                                    filtered_team["lastTen"] = f"{sr["wins"]}-{sr["losses"]}"

            if league_name == 'American League':
                mlb_leagues_standings["american_league"].append(filtered_team)
            elif league_name == 'National League':
                mlb_leagues_standings["national_league"].append(filtered_team)

        mlb_leagues_standings["american_league"].sort(key=lambda x: int(x["league_rank"]))
        mlb_leagues_standings["national_league"].sort(key=lambda x: int(x["league_rank"]))
        
        return {
            "ok": True,
            "error": None,
            "data": mlb_leagues_standings
        }

    except Exception as e:
        response.status_code = 500
        return {
            "ok": False,
            "data": None,
            "error": str(e)
        }
    
@app.get('/api/MLB/players')
def get_players(response: Response):
    response.headers["Cache-Control"] = 'public, s-maxage=84600'
    try:
        current_date = datetime.now().date()
        current_year_season = datetime.now().year
        next_year_season = current_year_season + 1

        mlb = mlbstatsapi.Mlb()
        # fetch players to query for player team
        players_list = mlb.get_people(sport_id=1,season=current_year_season)
        # fetch team for player team and team id
        teams_list = mlb.get_teams(sport_id=1,season=current_year_season)

        # players = statsapi.league_leaders(leaderCategories='avg',statGroup='hitting',limit=30)
        # mlbstatsapi doesn't provide allstar endpoints. need to create own request using the base url
        url_al = f"https://statsapi.mlb.com/api/v1/league/103/allStarFinalVote?season={current_year_season}"
        url_nl = f"https://statsapi.mlb.com/api/v1/league/104/allStarFinalVote?season={current_year_season}"
        allstar_al = requests.get(url_al).json()
        allstar_nl = requests.get(url_nl).json()
        
        def create_allstar_list(list):
            result = []
            for i in range(len(list)):
                team_id = None
                # get player team id
                for p in players_list:
                    if p.id == list[i]["id"]:
                        team_id = p.currentteam["id"]
                        break
                    
                team_name = None
                team_clubname = None
                # get player team name/clubname
                for team in teams_list:
                    if team_id == team.id:
                        team_clubname = team.clubname
                        team_name = team.name
                        break
                filtered_player_data = {
                    "player_name": list[i]["fullName"],
                    "player_id": list[i]["id"],
                    "player_position": list[i]["primaryPosition"]["name"],
                    "player_batside": list[i]["batSide"],
                    "player_pitchhand": list[i]["pitchHand"],
                    "team_name": team_name,
                    "team_clubname": team_clubname,
                    "team_id": team_id,
                }

                result.append(filtered_player_data)

            return result

        allstar_nl_list  =  allstar_nl["people"]
        allstar_al_list  =  allstar_al["people"]
        result_nl = create_allstar_list(allstar_nl_list)
        result_al = create_allstar_list(allstar_al_list)

        playerlist = []
        result_nl_copy = result_nl.copy()
        result_al_copy = result_al.copy()
        for i in range(34):
            if i % 2 == 0:
                for player in result_nl_copy:
                    playerlist.append(player)
                    result_nl_copy.remove(player)
                    break
            else:
                for player in result_al_copy:
                    playerlist.append(player)
                    result_al_copy.remove(player)
                    break
                
        return {
            "ok": True,
            "error": None,
            "data": playerlist
        }
    
    except Exception as e:
        response.status_code = 500
        return {
            "ok": False,
            "data": None,
            "error": str(e)
        }

# soccer data
FOOTBALL_DATA_URL = os.getenv("FOOTBALL_DATA_URL")
FOOTBALL_DATA_APIKEY = os.getenv("FOOTBALL_DATA_APIKEY")
@app.get('/api/SOCCER/schedules')
def get_schedules(response: Response):
    response.headers["Cache-Control"] = 'public, s-maxage=31536000'
    try:
        current_year = datetime.now().year
        PL_ID = 2021
        url = f"{FOOTBALL_DATA_URL}/competitions/{PL_ID}/matches"
        params = {
            "season": current_year
        }
        headers ={
            "X-Auth-Token": FOOTBALL_DATA_APIKEY
        }

        result = requests.get(url, headers=headers, params=params)
        result = result.json()
        
        schedules = []
        games_list = []
        for match in result["matches"]:
            label = match.get('stage').split('_')
            label = " ".join(label).title()
            date = match.get("utcDate").split('T')[0]
            timeUTC = match.get("utcDate").split('T')[1][0:-1]

            filtered_game_data = {
                "gameId": match.get("id"),
                "gameDate": date,
                "gameStatus": match.get("status"),
                "gameLabel": label,
                "homeTeam_name": match.get("homeTeam")["shortName"],
                "homeTeam_id": match.get("homeTeam")["id"],
                "homeTeam_crest": match.get("homeTeam")["crest"],
                "homeTeam_score": match.get("score")["fullTime"]["home"],
                "awayTeam_name": match.get("awayTeam")["shortName"],
                "awayTeam_id": match.get("awayTeam")["id"],
                "awayTeam_crest": match.get("awayTeam")["crest"],
                "awayTeam_score": match.get("score")["fullTime"]["away"],
                "gameTimeUTC": timeUTC,
            }
            
            games_list.append(filtered_game_data)
        for date, group_games in groupby(games_list, key=lambda x: x["gameDate"]):
            schedules.append({
                "date": date,
                "gamesList": list(group_games)
            })
        return {
            "ok": True,
            "error": None,
            "data": schedules
        }
    
    except Exception as e:
        response.status_code = 500
        return {
            "ok": False,
            "data": None,
            "error": str(e)
        }

@app.get('/api/SOCCER/standings')
def get_standings(response: Response):
    response.headers["Cache-Control"] = 'public, s-maxage=3600'
    try:
        current_year = datetime.now().year
        PL_ID = 2021
        url = f"{FOOTBALL_DATA_URL}/competitions/{PL_ID}/standings"
        params = {
            "season": current_year
        }
        headers ={
            "X-Auth-Token": FOOTBALL_DATA_APIKEY
        }
        
        result = requests.get(url,headers=headers, params=params)
        result = result.json()
    
        standings_list = []

        for team in result["standings"][0]["table"]:
            filtered_team_data = {
                "team_name": team.get("team")["name"],
                "team_clubname": team.get("team")["shortName"],
                "team_id": team.get("team")["id"],
                "team_crest": team.get("team")["crest"],
                "ties": team.get("draw"),
                "wins": team.get("won"),
                "losses": team.get("lost"),
                "league_rank": team.get("position"),
                "winpct": None,
                "last_five": team.get('form'),
                "goal_difference": team.get('goalDifference'),
                "points": team.get('points'),
                "goals_total": team.get('goalsFor'),
                "goals_against": team.get('goalsAgainst'),
                "league_name": result['competition']["name"],
                "league_id": result['competition']["id"],
                "league_crest": result['competition']["emblem"],
                "season": result['filters']["season"]
            }
            standings_list.append(filtered_team_data)

        return {
            "ok": True,
            "error": None,
            "data": standings_list
        }
    
    except Exception as e:
        response.status_code = 500
        return {
            "ok": False,
            "data": None,
            "error": str(e)
        }

@app.get('/api/SOCCER/players')
def get_players(response: Response):
    response.headers["Cache-Control"] = 'public, s-maxage=84600'
    try:
        current_year=datetime.now().year
        # pre-selected league/competition. later, implement a selectable dropdown for different competitions
        PL_ID = 2021
        url = f"{FOOTBALL_DATA_URL}/competitions/{PL_ID}/scorers"
        params = {
            "season": current_year,
            "limit": 20
        }
        headers ={
            "X-Auth-Token": FOOTBALL_DATA_APIKEY
        }

        result = requests.get(url,headers=headers, params=params)
        result = result.json()
        
        playerlist = []

        for p in result["scorers"]:
            filtered_player_data ={
                "player_name": f"{p["player"].get("name")}".strip(),
                "player_id": p["player"].get("id"),
                "player_position": p["player"].get("section"),
                "team_name": p["team"].get("name"),
                "team_clubname": p["team"].get("shortName"),
                "team_id": p["team"].get("id"),
                "team_crest": p["team"].get("crest")
            }
            playerlist.append(filtered_player_data)

        return {
            "ok": True,
            "error": None,
            "data": playerlist
        }
    
    except Exception as e:
        response.status_code = 500
        return {
            "ok": False,
            "data": None,
            "error": str(e)
        }
