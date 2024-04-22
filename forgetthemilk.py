import json
import argparse
from json.decoder import JSONDecodeError
import csv
import datetime

# TODO - might need to split by "project" (RTM list)
# TODO - make sure to follow CSV template provided by Todoist
# TODO - make sure completed tasks are imported as such and not as active tasks
# TODO - need to sign up for pro plan to increase project limit from 5
# TODO - mind the limits for 300 active tasks


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "rtm_json", help="The JSON file you exported from Remember The Milk"
    )
    parser.add_argument(
        "csv_incomplete",
        help="CSV file you want your converted *incomplete* RTM tasks written to",
    )
    parser.add_argument(
        "csv_completed",
        help="CSV file you want your converted *completed* RTM tasks written to",
    )
    return parser.parse_args()


def date_from_int(date_int):
    try:
        d = int(date_int) / 1000
        return datetime.datetime.fromtimestamp(d).strftime("%Y-%m-%d")
    except ValueError:
        return ""


def format_date(date_str):
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


def write_notes(writer, url, date_created, date_modified, location, mylist, tags):
    notes = []
    # TODO add metadata to notes, if set
    for k, v in {
        "url": url,
        "created": date_created,
        "modified": date_modified,
        "location": location,
        "mylist": mylist,
        "tags": tags,
    }.items():
        if v:
            notes.append(f"{k}: {v}")

    # FIXME insert newlines - maybe requires quotes around the field
    notes = "; ".join(notes)

    if notes:
        # write notes to line after task
        writer.writerow(
            [
                "Note",  # "TYPE", # Task | Note
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
    finally:
        return ";".join(task_tags)


def compile_notes(notes, task):
    try:
        # Compile notes with the same series_id as task.series_id
        task_notes = [
            note for note in notes if note.get("series_id") == task.get("series_id")
        ]

    except Exception as e:
        print(f"Error processing notes: {e}", task)
    finally:
        # print("task_notes", task_notes)
        return task_notes


def get_description(notes):
    # FIXME insert newlines - maybe requires quotes around the field
    return "\\n".join(
        [
            note.get("content", "").replace("\n", "\\n").replace("\r", "\\n")
            for note in notes
        ]
    )


def parse_due_date(due_date):
    if due_date:
        # TODO parse recurring tasks if "repeat" is not null, in which case it is a semi-colon separated list of:
        # FREQ=DAILY|MONTHLY|WEEKLY|YEARLY
        # INTERVAL=1|2|3|4|90
        # COUNT=4
        # BYDAY=TH
        # WKST=SU
        pass

    return due_date


def write_tasks(writer, name, description, due_date, priority, indent=1):
    # Write task details to CSV
    writer.writerow(
        [
            # TODO match to Todoist CSV template
            "Task",  # "TYPE", # Task | Note # TODO write notes to line after task
            name,  # "CONTENT", # Task Name or Note Content
            description,  # "DESCRIPTION", # Notes # TODO determine from task notes
            priority,  # "PRIORITY", # 1-4 # TODO determine from task priority
            indent,  # "INDENT", # 1-4 # TODO determine from task indent
            None,  # "AUTHOR", # User
            None,  # "RESPONSIBLE", # User
            due_date,  # "DATE", # Due Date # TODO determine from task due date; set recurring tasks if "repeat_every": true,
            "en" if due_date is not None else None,  # "DATE_LANG",
            None,  # "TIMEZONE", # UTC # TODO determine from user settings
            None,  # "DURATION", # 0 # TODO determine from task duration
            None,  # "DURATION_UNIT", # day # TODO determine from task duration
        ]
    )


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


def write_data(writer, tasks, notes, locations, lists, tags):
    for task in tasks:
        # Extract task details
        try:
            name = task.get("name", "untitled")
            url = task.get("url", "")

            date_created = date_from_int(task.get("date_created", ""))
            date_modified = date_from_int(task.get("date_modified", ""))
            # indent = task.get("indent", 1)  # Default indent level

            due_date = date_from_int(task.get("date_due", ""))

            # TODO parse "estimate" if set => DURATION,DURATION_UNIT

            priority = get_priority_from_task(task)
            location = get_location_from_task(task, locations)
            mylist = get_list_from_task(task, lists)
            mytags = get_tags_from_task(task, tags)

            # Write task details to CSV
            task_notes = compile_notes(notes, task)

            # Combine the notes into a single string
            description = get_description(task_notes)

            # TODO parse "date_due_has_time" if set
            due_date = parse_due_date(due_date)

            write_tasks(writer, name, description, due_date, priority)

            # write notes to line after task
            write_notes(
                writer, url, date_created, date_modified, location, mylist, mytags
            )

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
            locations = data.get("locations", [])  # TODO
            lists = data.get("lists", [])  # TODO
            tags = data.get("tags", [])

        sort_tasks(tasks)

        # Split tasks based on whether 'date_completed' is present
        active_tasks = [t for t in tasks if not t.get("date_completed")]
        completed_tasks = [t for t in tasks if t.get("date_completed")]

        # Write active tasks to incomplete CSV
        write_tasks_to_csv(
            args.csv_incomplete, active_tasks, notes, locations, lists, tags
        )

        # Write completed tasks to completed CSV
        write_tasks_to_csv(
            args.csv_completed, completed_tasks, notes, locations, lists, tags
        )

    except (FileNotFoundError, JSONDecodeError) as e:
        print(f"Error processing files: {e}")


def write_tasks_to_csv(file_path, tasks, notes, locations, lists, tags):
    with open(file_path, "w", newline="") as csv_file:
        writer = csv.writer(csv_file)
        write_header(writer)
        write_data(writer, tasks, notes, locations, lists, tags)


def sort_tasks(tasks):
    # Sort tasks by date_completed DESC, date_due ASC, priority DESC, name ASC
    tasks.sort(
        key=lambda x: (
            x.get("date_completed", 0),
            x.get("date_due", 0),
            x.get("priority", "PN"),
            x.get("name", "untitled"),
        ),
        reverse=True,
    )


if __name__ == "__main__":
    args = parse_args()
    main(args)
