import time
import alkymi as alk

time_to_sleep_s = alk.arg(0, name="time_to_sleep_s", doc="The number of seconds to sleep")
messages = alk.arg(["Hello alkymi"], name="messages", doc="Messages to display")


@alk.recipe()
def sleep_and_print(time_to_sleep_s: int, messages: str) -> None:
    """
    Sleep for a number of seconds before printing one or more messages

    :param time_to_sleep_s: The number of seconds to sleep for
    :param messages: The messages to print
    """
    time.sleep(time_to_sleep_s)
    for message in messages:
        print(message)


@alk.recipe()
def print_only(messages: str) -> None:
    """
    Prints one or more messages

    :param messages: The messages to print
    """
    for message in messages:
        print(message)


def main():
    lab = alk.Lab("cli")
    lab.add_recipes(sleep_and_print, print_only)
    lab.register_arg(time_to_sleep_s)
    lab.register_arg(messages)
    lab.open()


if __name__ == "__main__":
    main()
