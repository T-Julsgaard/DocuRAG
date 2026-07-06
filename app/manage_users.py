#!/usr/bin/env python3
"""
User administration CLI.

Run from the app/ directory:
    python manage_users.py list
    python manage_users.py create <username> [--limit 1000000] [--admin]
    python manage_users.py generate <count> [--limit 1000000]
    python manage_users.py delete <username>
    python manage_users.py setlimit <username> <tokens>
    python manage_users.py setasklimit <username> <questions>
    python manage_users.py password <username>

Examples:
    python manage_users.py create alice --admin
    python manage_users.py generate 20
    python manage_users.py setlimit agent01 500000
"""

import sys
import secrets
import argparse
import getpass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import DB_PATH
from database import (
    init_db, create_user, delete_user, update_limit,
    update_password, get_user, all_users_with_usage, update_ask_daily_limit
)

init_db(DB_PATH)


def cmd_list(args):
    users = all_users_with_usage(DB_PATH)
    if not users:
        print("No users yet.")
        return
    print(f"\n{'Username':<20} {'Admin':<6} {'Limit/day':<12} {'Tokens today':<14} {'Created'}")
    print("-" * 72)
    for u in users:
        admin_mark = "yes" if u["is_admin"] else ""
        print(f"{u['username']:<20} {admin_mark:<6} {u['daily_token_limit']:<12,} {u['tokens_today']:<14,} {u['created_at']}")
    print()


def cmd_create(args):
    if get_user(DB_PATH, args.username):
        print(f"Error: user '{args.username}' already exists.")
        sys.exit(1)
    password = getpass.getpass(f"Password for '{args.username}': ")
    if not password:
        print("Error: password must not be empty.")
        sys.exit(1)
    create_user(DB_PATH, args.username, password, args.limit, args.admin)
    role = "admin" if args.admin else "user"
    print(f"OK — {role} '{args.username}' created (limit: {args.limit:,} tokens/day)")


def cmd_generate(args):
    generated = []
    for i in range(1, args.count + 1):
        username = f"agent{i:02d}"
        if get_user(DB_PATH, username):
            print(f"Skipping: '{username}' already exists")
            continue
        password = secrets.token_urlsafe(12)
        create_user(DB_PATH, username, password, args.limit, is_admin=False)
        generated.append((username, password))

    if not generated:
        print("No new users created.")
        return

    output_file = Path(__file__).parent / "generated_users.txt"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("Generated users\n")
        f.write(f"Daily token limit: {args.limit:,}\n\n")
        f.write(f"{'Username':<20} {'Password'}\n")
        f.write("-" * 40 + "\n")
        for username, password in generated:
            f.write(f"{username:<20} {password}\n")

    print(f"\nOK — {len(generated)} users created (limit: {args.limit:,} tokens/day)")
    print(f"\n{'Username':<20} {'Password'}")
    print("-" * 40)
    for username, password in generated:
        print(f"{username:<20} {password}")
    print(f"\nSaved to: {output_file}")


def cmd_delete(args):
    if not get_user(DB_PATH, args.username):
        print(f"Error: user '{args.username}' does not exist.")
        sys.exit(1)
    confirm = input(f"Delete '{args.username}'? (yes/no): ").strip().lower()
    if confirm != "yes":
        print("Cancelled.")
        return
    delete_user(DB_PATH, args.username)
    print(f"OK — user '{args.username}' deleted.")


def cmd_setlimit(args):
    if not get_user(DB_PATH, args.username):
        print(f"Error: user '{args.username}' does not exist.")
        sys.exit(1)
    update_limit(DB_PATH, args.username, args.tokens)
    print(f"OK — token limit for '{args.username}' set to {args.tokens:,}/day")


def cmd_setasklimit(args):
    if not get_user(DB_PATH, args.username):
        print(f"Error: user '{args.username}' does not exist.")
        sys.exit(1)
    update_ask_daily_limit(DB_PATH, args.username, args.questions)
    print(f"OK — daily Ask limit for '{args.username}' set to {args.questions}/day")


def cmd_password(args):
    if not get_user(DB_PATH, args.username):
        print(f"Error: user '{args.username}' does not exist.")
        sys.exit(1)
    password = getpass.getpass(f"New password for '{args.username}': ")
    if not password:
        print("Error: password must not be empty.")
        sys.exit(1)
    update_password(DB_PATH, args.username, password)
    print(f"OK — password for '{args.username}' updated.")


parser = argparse.ArgumentParser(description="User administration")
sub = parser.add_subparsers(dest="command")

sub.add_parser("list", help="List all users and today's token usage")

p_create = sub.add_parser("create", help="Create a user")
p_create.add_argument("username")
p_create.add_argument("--limit", type=int, default=1_000_000, help="Daily token limit (default: 1,000,000)")
p_create.add_argument("--admin", action="store_true", help="Grant admin rights")

p_gen = sub.add_parser("generate", help="Generate N users with random passwords")
p_gen.add_argument("count", type=int)
p_gen.add_argument("--limit", type=int, default=1_000_000, help="Daily token limit per user")

p_del = sub.add_parser("delete", help="Delete a user")
p_del.add_argument("username")

p_limit = sub.add_parser("setlimit", help="Update daily token limit")
p_limit.add_argument("username")
p_limit.add_argument("tokens", type=int)

p_asklimit = sub.add_parser("setasklimit", help="Update daily Ask question limit")
p_asklimit.add_argument("username")
p_asklimit.add_argument("questions", type=int)

p_pw = sub.add_parser("password", help="Change a user's password")
p_pw.add_argument("username")

args = parser.parse_args()

commands = {
    "list": cmd_list, "create": cmd_create, "generate": cmd_generate,
    "delete": cmd_delete, "setlimit": cmd_setlimit,
    "setasklimit": cmd_setasklimit, "password": cmd_password,
}

if args.command not in commands:
    parser.print_help()
    sys.exit(1)

commands[args.command](args)
