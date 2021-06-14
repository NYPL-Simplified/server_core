import datetime
import pytz

# datetime helpers
# As part of the python 3 conversion, the datetime object went through a
# subtle update that changed how UTC works. Find more information here:
# https://blog.ganssle.io/articles/2019/11/utcnow.html
# https://docs.python.org/3/library/datetime.html#aware-and-naive-objects

def datetime_utc(*args, **kwargs):
    """Return a datetime object but with UTC information from pytz.
    :return: datetime object
    """
    return to_naive_utc(datetime.datetime(*args, **kwargs, tzinfo=pytz.UTC))

def from_timestamp(ts):
    """Return a UTC datetime object from a timestamp.

    :return: datetime object
    """
    return to_naive_utc(datetime.datetime.fromtimestamp(ts, tz=pytz.UTC))

def utc_now():
    """Get the current time in UTC.

    :return: datetime object
    """
    return to_naive_utc(datetime.datetime.now(tz=pytz.UTC))

def to_utc(dt):
    """This converts a naive datetime object that represents UTC into
    an aware datetime object.

    :type dt: datetime.datetime
    :return: datetime object, or None if `dt` was None.
    """
    if dt is None:
        return None
    if isinstance(dt, datetime.date):
        # Dates don't have timezones.
        # TODO: Not sure about this, maybe it should become midnight.
        return dt
    if dt.tzinfo is None:
        return to_naive_utc(dt.replace(tzinfo=pytz.UTC))
    if dt.tzinfo == pytz.UTC:
        # Already UTC.
        return to_naive_utc(dt)
    return to_naive_utc(dt.astimezone(pytz.UTC))

def to_naive_utc(dt):
    """This tries really hard to convert a datetime object into a naive
    datetime object that represents UTC.
    """
    if dt is None:
        return dt

    if isinstance(dt, datetime.date) and not isinstance(dt, datetime.datetime):
        # Dates don't have timezones.
        # TODO: Not sure about this, maybe it should become midnight.
        return dt

    if dt.tzinfo is None:
        # Already naive; we can only assume it also already represents
        # UTC.
        return dt

    if dt.tzinfo != pytz.UTC:
        # Timezone-aware but not UTC. Convert to UTC.
        dt = to_utc(dt)

    # Now it's a timezone-aware UTC datetime. Remove the tzinfo to
    # make it naive.
    return dt.replace(tzinfo=None)

def strptime_utc(date_string, format):
    """Parse a string that describes a time but includes no timezone,
    into a timezone-aware datetime object set to UTC.

    :raise ValueError: If `format` expects timezone information to be
        present in `date_string`.
    """
    if '%Z' in format or '%z' in format:
        raise ValueError(
            "Cannot use strptime_utc with timezone-aware format {}".format(
                format
            )
        )
    return to_utc(datetime.datetime.strptime(date_string, format))
