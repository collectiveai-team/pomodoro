/** A local calendar month, as the heatmap's navigation unit (year, 1-12 month, Story 77). */
export interface MonthKey {
  year: number;
  month: number;
}

/** The month that follows `month`, rolling `year` over at the December/January boundary. */
export function nextMonth({ year, month }: MonthKey): MonthKey {
  return month === 12 ? { year: year + 1, month: 1 } : { year, month: month + 1 };
}

/** The month that precedes `month`, rolling `year` back at the January/December boundary. */
export function previousMonth({ year, month }: MonthKey): MonthKey {
  return month === 1 ? { year: year - 1, month: 12 } : { year, month: month - 1 };
}

/**
 * The month/year title shown above the grid, in the app's Leitura-italic slot (Story 77).
 * Built from the month name alone (rather than `Intl`'s combined `long`+`numeric` format, which
 * inserts "de" for `es`) and formatted in UTC so a local timezone behind UTC can't shift the
 * UTC-midnight anchor date back into the previous month.
 */
export function monthTitle({ year, month }: MonthKey): string {
  const formatter = new Intl.DateTimeFormat("es", { month: "long", timeZone: "UTC" });
  const monthName = formatter.format(new Date(Date.UTC(year, month - 1, 1)));
  return `${monthName.charAt(0).toUpperCase()}${monthName.slice(1)} ${year}`;
}
