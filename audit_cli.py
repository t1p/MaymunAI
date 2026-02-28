import argparse
import json

from audit_log import tail_audit_events


def main() -> None:
    parser = argparse.ArgumentParser(description='Audit CLI for MaymunAI runtime events')
    subparsers = parser.add_subparsers(dest='command', required=True)

    tail_parser = subparsers.add_parser('tail', help='Show last N audit events')
    tail_parser.add_argument('--n', type=int, default=50, help='Number of events to show')

    args = parser.parse_args()

    if args.command == 'tail':
        events = tail_audit_events(n=args.n)
        for event in events:
            print(json.dumps(event, ensure_ascii=False))


if __name__ == '__main__':
    main()

