import datetime
import holidays

from .data.observances import fun_observances_db


def get_calendar_events(target_date_str: str = None) -> dict:
    """
    Retrieves the current season, major holidays, and fun observances (like 'Pizza Day')
    to help generate timely coloring page themes.

    Args:
        target_date_str (str, optional): The target date in 'YYYY-MM-DD' format (e.g., '2025-12-25'). Defaults to today's date.

    Returns:
        dict: A dictionary containing context for the Creative Director:
            - season (str): The meteorological season (e.g., 'Winter', 'Spring', 'Summer', 'Autumn').
            - major_holidays (list[str]): A list of major holidays within a +/- 3 day window,
              including relative timing (e.g., ['Christmas (2 days away)']). Returns ['None nearby'] if empty.
            - fun_observance (str): A specific niche or fun observance for the day
              (e.g., 'National Pizza Day' or 'Penguin Awareness Day'). Returns 'None specific today' if no match.
            - suggestion_heuristic (list[str]): A list of creative prompt triggers based on the season
              (e.g., ['Snow', 'Cozy indoors']).
    """

    # 1. Setup Date (Robust Parsing)
    if target_date_str:
        try:
            target_date = datetime.date.fromisoformat(target_date_str)
        except ValueError:
            # Fallback if LLM sends a bad format
            target_date = datetime.date.today()
    else:
        target_date = datetime.date.today()

    month = target_date.month
    day = target_date.day
    year = target_date.year

    # 2. Determine Season (Northern Hemisphere)
    season = "Winter"
    if 3 <= month <= 5:
        season = "Spring"
    elif 6 <= month <= 8:
        season = "Summer"
    elif 9 <= month <= 11:
        season = "Autumn"

    # 3. Get Major Holidays (US + International defaults)
    # We use a window of +/- 3 days so the agent can plan slightly ahead or cover a recent event
    major_holidays = []
    us_holidays = holidays.US(years=year)

    # Check a 7-day window (3 days before, 3 days after) to capture "upcoming" vibes
    for offset in range(-3, 4):
        check_date = target_date + datetime.timedelta(days=offset)
        if check_date in us_holidays:
            event_name = us_holidays.get(check_date)
            # Filter out administrative holidays often not relevant to kids (optional)
            if "Veterans" not in event_name and "Columbus" not in event_name:
                status = (
                    "Today"
                    if offset == 0
                    else f"{abs(offset)} days {'ago' if offset < 0 else 'away'}"
                )
                major_holidays.append(f"{event_name} ({status})")

    # 4. Fun "Niche" Observances (Custom curated list for coloring themes)
    key = f"{month:02d}-{day:02d}"
    fun_event = fun_observances_db.get(key)

    # 5. Construct the Context Object
    context_data = {
        "current_date": target_date.isoformat(),
        "season": season,
        "major_holidays": major_holidays if major_holidays else ["None nearby"],
        "fun_observance": fun_event if fun_event else "None specific today",
        "suggestion_heuristic": [],
    }

    # 6. Add Heuristics to guide the LLM (Optional logic boost)
    if season == "Winter":
        context_data["suggestion_heuristic"].append(
            "Snow, cozy indoors, warm clothes, ice sports"
        )
    elif season == "Summer":
        context_data["suggestion_heuristic"].append(
            "Beach, sun, camping, insects, ice cream"
        )

    if fun_event:
        context_data["suggestion_heuristic"].append(
            f"Create something related to {fun_event}"
        )

    return context_data
