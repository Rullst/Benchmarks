//! Calendar dates without a dependency: days since 1970-01-01 (UTC) and back.

use std::fmt;
use std::time::{SystemTime, UNIX_EPOCH};

const MONTHS: [&str; 12] = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
];

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub struct Date {
    days: i64,
}

impl Date {
    /// `YYYY-MM-DD`, or the first ten characters of an ISO 8601 timestamp.
    pub fn parse(text: &str) -> Option<Date> {
        let text = text.get(..10)?;
        let bytes = text.as_bytes();
        if bytes[4] != b'-' || bytes[7] != b'-' {
            return None;
        }
        let year: i64 = digits(&text[..4])?;
        let month: i64 = digits(&text[5..7])?;
        let day: i64 = digits(&text[8..10])?;
        if !(1..=12).contains(&month) || day < 1 || day > days_in_month(year, month) {
            return None;
        }
        Some(Date { days: days_from_civil(year, month, day) })
    }

    /// Today's date in UTC.
    pub fn today() -> Date {
        let seconds = SystemTime::now().duration_since(UNIX_EPOCH).map(|d| d.as_secs()).unwrap_or(0);
        Date { days: (seconds / 86_400) as i64 }
    }

    pub fn days_since(self, earlier: Date) -> i64 {
        self.days - earlier.days
    }

    /// "20 November 2026".
    pub fn long(self) -> String {
        let (year, month, day) = civil_from_days(self.days);
        format!("{day} {} {year}", MONTHS[(month - 1) as usize])
    }
}

impl fmt::Display for Date {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        let (year, month, day) = civil_from_days(self.days);
        write!(f, "{year:04}-{month:02}-{day:02}")
    }
}

fn digits(text: &str) -> Option<i64> {
    if text.bytes().all(|b| b.is_ascii_digit()) { text.parse().ok() } else { None }
}

fn is_leap(year: i64) -> bool {
    (year % 4 == 0 && year % 100 != 0) || year % 400 == 0
}

fn days_in_month(year: i64, month: i64) -> i64 {
    match month {
        2 if is_leap(year) => 29,
        2 => 28,
        4 | 6 | 9 | 11 => 30,
        _ => 31,
    }
}

// Howard Hinnant's days_from_civil and civil_from_days.
fn days_from_civil(year: i64, month: i64, day: i64) -> i64 {
    let y = if month <= 2 { year - 1 } else { year };
    let era = y.div_euclid(400);
    let yoe = y - era * 400;
    let mp = (month + 9) % 12;
    let doy = (153 * mp + 2) / 5 + day - 1;
    let doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
    era * 146_097 + doe - 719_468
}

fn civil_from_days(days: i64) -> (i64, i64, i64) {
    let z = days + 719_468;
    let era = z.div_euclid(146_097);
    let doe = z - era * 146_097;
    let yoe = (doe - doe / 1460 + doe / 36_524 - doe / 146_096) / 365;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let day = doy - (153 * mp + 2) / 5 + 1;
    let month = if mp < 10 { mp + 3 } else { mp - 9 };
    let year = yoe + era * 400 + i64::from(month <= 2);
    (year, month, day)
}

#[cfg(test)]
mod tests {
    use super::Date;

    #[test]
    fn round_trips_and_rejects_bad_dates() {
        let date = Date::parse("2026-11-20T15:39:56Z").unwrap();
        assert_eq!(date.to_string(), "2026-11-20");
        assert_eq!(date.long(), "20 November 2026");
        assert_eq!(Date::parse("2024-02-29").unwrap().to_string(), "2024-02-29");
        assert!(Date::parse("2026-02-29").is_none());
        assert!(Date::parse("2026-13-01").is_none());
        assert!(Date::parse("20261120").is_none());
        assert_eq!(Date::parse("2027-01-01").unwrap().days_since(Date::parse("2026-12-31").unwrap()), 1);
    }
}
