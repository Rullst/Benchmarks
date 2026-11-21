//! Inline SVG bars of the ratios to Axum. Geometry is written as SVG attributes (never inline style),
//! so the pages keep `style-src 'self'`; the colours come from the stylesheet.

use rullst::html;
use rullst::html::Markup;

use crate::format::times;

/// A linear scale from 0 to a quarter step above the largest value (at least 1.25, so the 1.00 line of Axum
/// is always inside the bar area).
pub struct Scale {
    max: f64,
}

impl Scale {
    pub fn new(values: impl IntoIterator<Item = f64>) -> Scale {
        let top = values.into_iter().filter(|v| v.is_finite()).fold(1.0_f64, f64::max);
        let mut max = (top * 4.0).ceil() / 4.0;
        if max - top < 0.06 {
            max += 0.25;
        }
        Scale { max }
    }

    fn percent(&self, value: f64) -> f64 {
        (value / self.max * 100.0).clamp(0.0, 100.0)
    }

    #[cfg(test)]
    fn max(&self) -> f64 {
        self.max
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Tone {
    /// A ranked implementation.
    Ranked,
    /// Axum, the reference.
    Reference,
    /// A diagnostic or the A/A control.
    Unranked,
}

impl Tone {
    fn class(self) -> &'static str {
        match self {
            Tone::Ranked => "bar bar-ranked",
            Tone::Reference => "bar bar-reference",
            Tone::Unranked => "bar bar-unranked",
        }
    }
}

/// A horizontal bar for one score: longer is better; the vertical line marks Axum (1.00×). The value is
/// printed next to the bar by the caller, so the graphic is hidden from assistive technology.
pub fn bar(value: Option<f64>, scale: &Scale, tone: Tone, title: &str) -> Markup {
    let reference = format!("{:.2}%", scale.percent(1.0));
    let Some(value) = value else {
        return html! {
            <svg class="bar bar-empty" width="100%" height="16" aria-hidden="true" focusable="false">
                <rect class="bar-track" x="0" y="4" width="100%" height="8" rx="4" />
                <line class="bar-ref" x1={reference.as_str()} x2={reference.as_str()} y1="0" y2="16" />
            </svg>
        };
    };
    let width = format!("{:.2}%", scale.percent(value).max(0.35));
    let tip = format!("{title}: {}× Axum", times(value));
    html! {
        <svg class={tone.class()} width="100%" height="16" aria-hidden="true" focusable="false">
            <rect class="bar-track" x="0" y="4" width="100%" height="8" rx="4" />
            <rect class="bar-fill" x="0" y="4" width={width} height="8" rx="2"><title>{tip}</title></rect>
            <line class="bar-ref" x1={reference.as_str()} x2={reference.as_str()} y1="0" y2="16" />
        </svg>
    }
}

/// The scale above a column of bars: 0 and the 1.00 of Axum (the bars share one linear scale).
pub fn axis(scale: &Scale) -> Markup {
    let reference = format!("{:.2}%", scale.percent(1.0));
    html! {
        <svg class="bar-axis" width="100%" height="14" aria-hidden="true" focusable="false">
            <text x="0" y="11" class="axis-label">"0"</text>
            <text x={reference.as_str()} y="11" class="axis-label axis-ref" text-anchor="middle">"1.00×"</text>
        </svg>
    }
}

/// A small column chart of every ranked score in a category (sorted, highest first), for the category
/// cards. `highlight` marks the columns of Rullst as generated.
pub fn columns(scores: &[(f64, bool)], label: &str) -> Markup {
    let scale = Scale::new(scores.iter().map(|(s, _)| *s));
    let width = (scores.len().max(1) * 10) as f64;
    let height = 56.0;
    let view = format!("0 0 {width} {height}");
    let reference = format!("{:.2}", height - height * scale.percent(1.0) / 100.0);
    let bars: Markup = scores
        .iter()
        .enumerate()
        .map(|(i, (score, highlight))| {
            let h = (height * scale.percent(*score) / 100.0).max(0.8);
            let x = format!("{}", i * 10 + 1);
            let y = format!("{:.2}", height - h);
            let h = format!("{h:.2}");
            let class = if *highlight { "col col-rullst" } else { "col" };
            html! { <rect class={class} x={x} y={y} width="8" height={h} /> }
        })
        .collect();
    html! {
        <svg class="columns" viewBox={view} preserveAspectRatio="none" width="100%" height="56" role="img"
            aria-label={label}>
            {bars}
            <line class="col-ref" x1="0" x2={format!("{width}")} y1={reference.as_str()} y2={reference.as_str()} />
        </svg>
    }
}

#[cfg(test)]
mod tests {
    use super::Scale;

    #[test]
    fn scale_keeps_axum_inside_and_leaves_headroom() {
        assert_eq!(Scale::new([0.5, 0.2]).max(), 1.25);
        assert_eq!(Scale::new([1.19]).max(), 1.25);
        assert_eq!(Scale::new([1.22]).max(), 1.5);
        assert_eq!(Scale::new([1.6]).max(), 1.75);
    }
}
