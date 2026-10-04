"""CLI routing for the Python application."""

import argparse
import signal

from . import notifications
from .config import load_config, set_model
from .control import RunControl, request_stop
from .desktop import create_desktop
from .errors import AcademicError, Cancelled
from .gemini import GeminiClient
from .images import capture_png
from .runner import QuestionRunner
from .system import require_commands
from .vision import Vision


def positive_count(value):
    try:
        count = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("Enter an integer question count.") from None
    if not 1 <= count <= 10_000:
        raise argparse.ArgumentTypeError("Question count must be between 1 and 10000.")
    return count


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        prog="academic", description="Screenshot helper and Question Runner"
    )
    actions = result.add_mutually_exclusive_group()
    actions.add_argument(
        "--clear", "-c", action="store_true", help="Clear dunst notifications (Linux)"
    )
    actions.add_argument("--simulate", "-s", action="store_true", help="Preview notifications")
    actions.add_argument("--notify", metavar="TEXT", help="Send a notification")
    actions.add_argument("--set-model", metavar="MODEL", help="Update GEMINI_MODEL in .env")
    actions.add_argument(
        "--run", action="store_true", help="Start Question Runner in your current browser"
    )
    actions.add_argument("--stop", action="store_true", help="Request that Question Runner stop")
    result.add_argument(
        "--questions",
        type=positive_count,
        metavar="COUNT",
        help="Question Runner limit (otherwise prompted)",
    )
    result.add_argument(
        "--dry-run", action="store_true", help="Inspect the first question without clicking"
    )
    return result


def _terminated(_signal, _frame):
    raise Cancelled("Terminated by user.", 143)


def main(argv=None) -> int:
    arguments = parser()
    args = arguments.parse_args(argv)
    if (args.questions is not None or args.dry_run) and not args.run:
        arguments.error("--questions and --dry-run require --run")
    previous = signal.signal(signal.SIGTERM, _terminated)
    runner = None
    try:
        if args.clear:
            notifications.clear()
        elif args.simulate:
            notifications.simulate()
        elif args.notify is not None:
            notifications.notify(args.notify)
        elif args.set_model is not None:
            path = set_model(args.set_model)
            print(f"GEMINI_MODEL={args.set_model} saved to {path}")
        elif args.stop:
            request_stop()
            print("Stop requested. No new actions will start after the current operation returns.")
        else:
            count = args.questions
            if args.run and count is None:
                try:
                    count = positive_count(input("How many questions? "))
                except argparse.ArgumentTypeError as error:
                    raise AcademicError(str(error)) from None
            config = load_config()
            require_commands("curl")
            client = GeminiClient(config)
            if args.run:
                if count is None:
                    raise AcademicError("Question Runner requires a question count.")
                desktop = create_desktop()
                with RunControl() as control:
                    runner = QuestionRunner(desktop, Vision(client), check=control.check)
                    result = runner.run(count, dry_run=args.dry_run)
                print(f"Stopped after {result.answered}/{result.requested}: {result.reason}")
                return 0 if result.complete or args.dry_run else 1
            answer = client.generate(capture_png())
            notifications.notify(answer)
        return 0
    except (KeyboardInterrupt, Cancelled) as error:
        answered = runner.answered if runner else 0
        print(f"Stopped by user after {answered} verified questions.")
        return error.exit_code if isinstance(error, Cancelled) else 130
    except EOFError:
        notifications.report_error("No question count received.")
        return 1
    except (AcademicError, OSError) as error:
        message = (
            str(error)
            if isinstance(error, AcademicError)
            else "A local file or desktop operation failed."
        )
        if runner is not None:
            message = f"Stopped after {runner.answered} verified questions: {message}"
        notifications.report_error(message)
        return 1
    finally:
        signal.signal(signal.SIGTERM, previous)
