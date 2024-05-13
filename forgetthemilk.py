#!/usr/bin/env python3

import json
import argparse
from json.decoder import JSONDecodeError
import csv
import datetime
import re


"""
- make sure to follow CSV template provided by Todoist
- split by "project" (RTM list)
- make sure completed tasks are imported as such and not as active tasks
"""

# NEWLINE = "\\n"
NEWLINE = "\n"


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "rtm_json",
        help="The JSON file you exported from Remember The Milk",
        default="rtm.json",
    )
    parser.add_argument(
        "csv_incomplete",
        help="CSV file you want your converted *incomplete* RTM tasks written to",
        default="out.csv",
        nargs="?",
    )
    parser.add_argument(
        "csv_completed",
        help="CSV file you want your converted *completed* RTM tasks written to",
        default="completed.csv",
        nargs="?",
    )
    return parser.parse_args()


def date_from_int(date_int):
    try:
        d = int(date_int) / 1000
        return datetime.datetime.fromtimestamp(d).strftime("%Y-%m-%d")
    except ValueError:
        return ""


def format_date(date_str):
    if not date_str:
        return None
    try:
        date_obj = datetime.datetime.strptime(date_str, "%Y-%m-%d")
        return date_obj.strftime("%Y-%m-%d")
    except ValueError:
        return ""


def write_header(writer):
    writer.writerow(
        [
            "TYPE",
            "CONTENT",
            "DESCRIPTION",
            "PRIORITY",
            "INDENT",
            "AUTHOR",
            "RESPONSIBLE",
            "DATE",
            "DATE_LANG",
            "TIMEZONE",
            "DURATION",
            "DURATION_UNIT",
        ]
    )


def get_location_from_task(task, locations):
    result = None
    try:
        location_id = task.get("location_id")
        for location in locations:
            if location["id"] == location_id:
                return location["name"]
    except Exception as e:
        print(f"Error processing location: {e}", task)
    return result


def get_list_from_task(task, lists):
    result = None
    try:
        list_id = task.get("list_id", "")
        if list_id != "":
            for lst in lists:
                if lst["id"] == list_id:
                    # print("lst", lst)
                    return lst["name"]
    except Exception as e:
        print(f"Error processing list_id: {e}", task)
    return result


def write_notes(writer, url, date_created, date_modified, location, list, tags):
    notes = []
    """add metadata to notes, if set"""
    for k, v in {
        # "url": url,
        "created": date_created,
        "modified": date_modified,
        # "location": location,
        # "list": list,
        # "tags": tags,
    }.items():
        if v:
            notes.append(f"{k}: {v}")

    notes = NEWLINE.join(notes)

    if notes:
        # write notes to line after task
        writer.writerow(
            [
                "note",  # "TYPE", # Task | Note
                notes,  # "CONTENT"
                None,  # "DESCRIPTION"
                None,  # "PRIORITY"
                None,  # "INDENT"
                None,  # "AUTHOR"
                None,  # "RESPONSIBLE"
                None,  # "DATE"
                None,  # "DATE_LANG"
                None,  # "TIMEZONE"
                None,  # "DURATION"
                None,  # "DURATION_UNIT"
            ]
        )


def get_tags_from_task(task, tags):
    try:
        task_tags = [tag for tag in tags if tag.get("tag_id") in task.get("tags", [])]
    except Exception as e:
        print(f"Error processing tags: {e}", task)
        task_tags = []

    return task_tags


def compile_notes(notes, task):
    try:
        # Compile notes with the same series_id as task.series_id
        task_notes = [
            note for note in notes if note.get("series_id") == task.get("series_id")
        ]

    except Exception as e:
        print(f"Error processing notes: {e}", task)
        task_notes = []

    # print("task_notes", task_notes)
    return task_notes


def get_description(url, notes):
    description = ""
    if url:
        description += url + NEWLINE
    description += NEWLINE.join(
        [
            note.get("content", "").replace("\n", NEWLINE).replace("\r", NEWLINE)
            for note in notes
        ]
    )

    description = replace_urls_with_markdown(description)
    return description


def replace_urls_with_markdown(text):
    """Replace all bare URLs in the text with Markdown links, skipping already formatted ones."""
    # Regex to match URLs that are not already in Markdown link format
    # This regex looks for URLs that are not preceded by '(' or ']' and not followed by ')'
    url_pattern = re.compile(r"(?<!\()https?://\S+(?!\))")

    # Replace each URL with its Markdown equivalent
    def replacement(match):
        url = match.group(0)
        clean_url = re.sub(r"^https?://", "", url)  # Strip 'http://' or 'https://'
        clean_url = re.sub(r"/$", "", clean_url)  # Strip trailing slash
        clean_url = re.sub(r"^www\.", "", clean_url)  # Strip 'www.'
        return f"[{clean_url}]({url})"

    # Use re.sub with a function to avoid replacing already formatted URLs
    return re.sub(url_pattern, replacement, text)


def write_tasks(
    writer, name, description, due_date, priority, duration, duration_unit, indent=1
):
    """
    Write task details to CSV
    formatted according to Todoist CSV template
    """
    writer.writerow(
        [
            "task",  # "TYPE", # Task | Note # write notes to line after task
            name,  # "CONTENT", # Task Name or Note Content
            description,  # "DESCRIPTION", # Notes # determined from task notes
            priority,  # "PRIORITY", # 1-4 # determined from task priority
            indent,  # "INDENT", # 1-4 # TODO determine from task indent
            None,  # "AUTHOR", # User
            None,  # "RESPONSIBLE", # User
            due_date,  # "DATE", # Due Date # FIXME determine from task due date; set recurring tasks if "repeat_every": true,
            "en" if due_date is not None else None,  # "DATE_LANG",
            None,  # "TIMEZONE", # UTC # TODO determine from user settings
            duration,  # "DURATION", # 0 # determine from task duration
            duration_unit,  # "DURATION_UNIT", # day # determine from task duration
        ]
    )


def parse_iso_duration(iso_str):
    """Parse ISO 8601 duration strings to total minutes."""
    # Regex to extract time units from ISO 8601 duration strings
    pattern = re.compile(r"PT(?:(\d+)H)?(?:(\d+)M)?")
    match = pattern.match(iso_str)
    if match:
        hours, minutes = match.groups(default="0")
        total_minutes = int(hours) * 60 + int(minutes)
        return total_minutes
    return 0  # Return 0 minutes if no pattern matched


def get_estimate_from_task(task):
    duration = task.get("estimate", "")
    if not duration:
        return None, None

    # Check if duration is in ISO 8601 format
    if duration.startswith("PT"):
        total_minutes = parse_iso_duration(duration)
        return total_minutes, "minute" if total_minutes else (None, None)

    return None, None


def get_priority_from_task(task):
    p = task.get("priority", None)
    if p == "P1":
        return 1
    elif p == "P2":
        return 2
    elif p == "P3":
        return 3
    elif p == "PN":
        return 4
    return None


def parse_recurrence(repeat):
    repeat_parsed = {}
    if repeat:
        repeat_parts = repeat.split(";")
        for part in repeat_parts:
            key, value = part.split("=")
            repeat_parsed[key] = value

    if repeat_parsed:
        freq = repeat_parsed.get("FREQ", "")
        interval = repeat_parsed.get("INTERVAL", "")
        count = repeat_parsed.get("COUNT", "")
        byday = repeat_parsed.get("BYDAY", "")
        wkst = repeat_parsed.get("WKST", "")

        return {
            "freq": freq,
            "interval": interval,
            "count": count,
            "byday": byday,
            "wkst": wkst,
        }

    return None


def date_short_to_long(day):
    if day == "MO":
        return "Monday"
    if day == "TU":
        return "Tuesday"
    if day == "WE":
        return "Wednesday"
    if day == "TH":
        return "Thursday"
    if day == "FR":
        return "Friday"
    if day == "SA":
        return "Saturday"
    if day == "SU":
        return "Sunday"
    return day


def period_short_to_long(period):
    if period == "DAILY":
        return "day"
    if period == "WEEKLY":
        return "week"
    if period == "MONTHLY":
        return "month"
    if period == "YEARLY":
        return "year"
    return period


def parse_due_date(due_date, date_due_has_time, repeat, repeat_every):
    # TODO add support for date_due_has_time
    if due_date:
        due_date = date_from_int(due_date)
        due_date = format_date(due_date)

        if repeat:
            """
            parse recurring tasks if "repeat" is not null, in which case it is a semi-colon separated list of:
            # FREQ=DAILY|MONTHLY|WEEKLY|YEARLY
            # INTERVAL=1|2|3|4|90
            # COUNT=4
            # BYDAY=MO|TU|WE|TH|FR|SA|SU
            # WKST=MO|TU|WE|TH|FR|SA|SU
            """
            recurrence = parse_recurrence(repeat)

            if recurrence:
                # translate into Todoist CSV task shorthand

                result = []

                if recurrence.get("interval"):
                    result.append("every")
                    if int(recurrence.get("interval") or 0) > 1:
                        result.append(recurrence.get("interval"))
                    if recurrence.get("byday"):
                        result.append(date_short_to_long(recurrence.get("byday")))
                    else:
                        result.append(period_short_to_long(recurrence.get("freq")))
                else:
                    result.append(recurrence.get("freq"))

                if due_date:
                    result.append(f"starting {due_date}")

                return due_date, " ".join(result)

        return due_date, None

    return None, None


def get_due_date_from_task(task):
    # "date_due": 1629842400000,
    # "date_due_has_time": false,
    # "repeat": "FREQ=DAILY;INTERVAL=1;WKST=SU",
    # "repeat_every": false,

    due_date = task.get("date_due", "")
    if due_date:
        repeat_every = task.get("repeat_every", False)
        date_due_has_time = task.get("date_due_has_time", False)
        repeat = task.get("repeat", "")
        due_date, recurrence = parse_due_date(
            due_date, date_due_has_time, repeat, repeat_every
        )
        return due_date, recurrence
    return None, None


def write_data(writer, tasks, notes, all_locations, all_lists, all_tags):
    for task in tasks:
        # Extract task details
        try:
            name = task.get("name", "untitled")
            url = task.get("url", "")

            date_created = date_from_int(task.get("date_created", ""))
            date_modified = date_from_int(task.get("date_modified", ""))
            indent = task.get("indent", 1)  # Default indent level

            due_date, recurrence = get_due_date_from_task(task)
            duration, duration_unit = get_estimate_from_task(task)
            priority = get_priority_from_task(task)
            location = get_location_from_task(task, all_locations)
            list = get_list_from_task(task, all_lists)
            tags = get_tags_from_task(task, all_tags)

            # add labels and lists to task names
            name = annotate_task(name, location, list, tags, recurrence)

            # Write task details to CSV
            task_notes = compile_notes(notes, task)

            # Combine the notes into a single string
            description = get_description(url, task_notes)

            write_tasks(
                writer,
                name,
                description,
                due_date,
                priority,
                duration,
                duration_unit,
                indent,
            )

            # write notes to line after task
            write_notes(writer, url, date_created, date_modified, location, list, tags)

        except Exception as e:
            print(f"Error processing task: {e}", task)


def main(args):
    try:
        with open(args.rtm_json, "r") as json_file:
            data = json.load(json_file)

            # activities = data.get("activities", [])
            # apps = data.get("apps", [])
            # attachments = data.get("attachments", [])
            # config = data.get("config", [])
            # contacts = data.get("contacts", [])
            # drag_drop = data.get("drag_drop", [])
            # external_auths = data.get("external_auths", [])
            # favorites = data.get("favorites", [])
            # file_services = data.get("file_services", [])
            # list_permissions = data.get("list_permissions", [])
            # notification_sinks = data.get("notification_sinks", [])
            # reminders = data.get("reminders", [])
            # requests = data.get("requests", [])
            # scripts = data.get("scripts", [])
            # smart_lists = data.get("smart_lists", [])
            # sorting_schemes = data.get("sorting_schemes", [])
            tasks = data.get("tasks", [])
            notes = data.get("notes", [])
            locations = data.get("locations", [])
            lists = data.get("lists", [])
            tags = data.get("tags", [])

        sort_tasks(tasks)
        # tasks = group_tasks(tasks)
        tasks = remove_duplicates(tasks)

        # Split tasks based on whether 'date_completed' is present
        active_tasks = [t for t in tasks if not t.get("date_completed")]
        completed_tasks = [t for t in tasks if t.get("date_completed")]

        # Write active tasks to incomplete CSV
        # loop through lists
        # for each list, write tasks to CSV; include format_label(list name) in CSV name, before .csv
        for lst in lists:
            list_name = format_label(lst.get("name"))
            csv_incomplete = f"{args.csv_incomplete}_{list_name}.csv"
            print(f"Writing {list_name} tasks to {csv_incomplete}")
            tasks_for_list = [
                t for t in active_tasks if t.get("list_id") == lst.get("id")
            ]
            if tasks_for_list.__len__() > 0:
                write_tasks_to_csv(
                    csv_incomplete,
                    tasks_for_list,
                    notes,
                    locations,
                    lists=[lst],
                    tags=tags,
                )

        # write_tasks_to_csv(
        #     args.csv_incomplete, active_tasks, notes, locations, lists, tags
        # )

        # Write completed tasks to completed CSV
        write_tasks_to_csv(
            args.csv_completed, completed_tasks, notes, locations, lists, tags
        )

    except (FileNotFoundError, JSONDecodeError) as e:
        print(f"Error processing files: {e}")


def format_label(label):
    """remove non-alphanumeric characters"""
    # Regex pattern to match emojis
    emoji_pattern = re.compile(
        "["
        "\U0001f600-\U0001f64f"  # emoticons
        "\U0001f300-\U0001f5ff"  # symbols & pictographs
        "\U0001f680-\U0001f6ff"  # transport & map symbols
        "\U0001f700-\U0001f77f"  # alchemical symbols
        "\U0001f780-\U0001f7ff"  # Geometric Shapes Extended
        "\U0001f800-\U0001f8ff"  # Supplemental Arrows-C
        "\U0001f900-\U0001f9ff"  # Supplemental Symbols and Pictographs
        "\U0001fa00-\U0001fa6f"  # Chess Symbols
        "\U0001fa70-\U0001faff"  # Symbols and Pictographs Extended-A
        "\U00002702-\U000027b0"  # Dingbats
        "\U000024c2-\U0001f251"
        "]+",
        flags=re.UNICODE,
    )

    # Remove emojis
    label = emoji_pattern.sub("", label)

    # Replace non-allowed characters with underscore
    sanitized_label = re.sub(r"[^a-zA-Z0-9_-]+", "_", label)
    sanitized_label = sanitized_label.strip("_")
    return sanitized_label


def annotate_task(name, location, list, tags, recurrence):
    """add labels and lists to task name"""

    task = " ".join(
        [
            name,
            f"@{format_label(location)}" if location is not None else "",
            f"@{format_label(list)}" if list is not None else "",
            f"{recurrence}" if recurrence is not None else "",
            " ".join([f"#{format_label(tag)}" for tag in tags])
            if tags is not None
            else "",
        ]
    )

    return task.strip()


def write_tasks_to_csv(file_path, tasks, notes, locations, lists, tags):
    with open(file_path, "w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        write_header(writer)
        write_data(writer, tasks, notes, locations, lists, tags)


def sort_tasks(tasks):
    # Sort tasks by date_completed DESC, date_due ASC, priority DESC, name ASC
    tasks.sort(
        key=lambda x: (
            x.get("date_completed", 0),
            x.get("list_id", ""),
            x.get("date_due", 0),
            x.get("priority", "4"),
            x.get("name", ""),
        ),
        reverse=True,
    )


def remove_duplicates(tasks):
    """
    remove duplicate tasks
    if task is not completed, only keep the most recent one
    """
    seen = set()
    unique_tasks = []
    for task in tasks:
        task_name = task.get("name")
        series_id = task.get("series_id")
        date_completed = task.get("date_completed")

        if task_name:
            if series_id and not date_completed:
                if series_id not in seen:
                    seen.add(series_id)
                    unique_tasks.append(task)
            else:
                unique_tasks.append(task)
    return unique_tasks


def group_tasks(tasks):
    """group tasks by task name and series_id; indent = 2 for subtasks"""
    grouped_tasks = {}
    for task in tasks:
        task_name = task.get("name")
        series_id = task.get("series_id")
        if task_name and series_id:
            if task_name not in grouped_tasks:
                grouped_tasks[task_name] = []
            grouped_tasks[task_name].append(task)

    # Set indent level for subsequent tasks with the same name
    for task_name, task_list in grouped_tasks.items():
        for i, task in enumerate(task_list):
            if i > 0:
                task["indent"] = 2

    return tasks


if __name__ == "__main__":
    args = parse_args()
    main(args)
