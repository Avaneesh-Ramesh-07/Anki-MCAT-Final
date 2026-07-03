<!--
Copyright: Ankitects Pty Ltd and contributors
License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
-->
<!--
Combined "Statistics" page. Two accordion sections layered on the shared MCAT
"calm sketchbook" design system: MCAT Readiness on top (open by default), and
Anki's normal graphs below. Both components already exist elsewhere — this
route only wraps/embeds them, never reimplements them.
-->
<script lang="ts">
    import "$lib/mcat/theme.scss";

    import type { PageData } from "./$types";

    // Readiness dashboard (owned by the readiness route).
    import ReadinessDashboard from "../readiness/ReadinessDashboard.svelte";

    // Anki's normal graphs (owned by the graphs route). GraphsPage fetches its
    // own data via the `graphs` RPC; it only needs the component list + search.
    import AddedGraph from "../graphs/AddedGraph.svelte";
    import ButtonsGraph from "../graphs/ButtonsGraph.svelte";
    import CalendarGraph from "../graphs/CalendarGraph.svelte";
    import CardCounts from "../graphs/CardCounts.svelte";
    import DifficultyGraph from "../graphs/DifficultyGraph.svelte";
    import EaseGraph from "../graphs/EaseGraph.svelte";
    import FutureDue from "../graphs/FutureDue.svelte";
    import GraphsPage from "../graphs/GraphsPage.svelte";
    import HourGraph from "../graphs/HourGraph.svelte";
    import IntervalsGraph from "../graphs/IntervalsGraph.svelte";
    import RangeBox from "../graphs/RangeBox.svelte";
    import RetrievabilityGraph from "../graphs/RetrievabilityGraph.svelte";
    import ReviewsGraph from "../graphs/ReviewsGraph.svelte";
    import StabilityGraph from "../graphs/StabilityGraph.svelte";
    import TodayStats from "../graphs/TodayStats.svelte";
    import TrueRetention from "../graphs/TrueRetention.svelte";

    export let data: PageData;

    const graphs = [
        TodayStats,
        FutureDue,
        CalendarGraph,
        ReviewsGraph,
        CardCounts,
        IntervalsGraph,
        StabilityGraph,
        EaseGraph,
        DifficultyGraph,
        RetrievabilityGraph,
        TrueRetention,
        HourGraph,
        ButtonsGraph,
        AddedGraph,
    ];
</script>

<div class="mcat stats-page">
    <div class="stats-shell">
        <h1>Statistics</h1>

        <details class="accordion" open>
            <summary>
                <span class="summary-title">MCAT Readiness</span>
                <svg
                    class="chevron"
                    viewBox="0 0 24 24"
                    aria-hidden="true"
                    focusable="false"
                >
                    <path
                        d="M6 9l6 6 6-6"
                        fill="none"
                        stroke="currentColor"
                        stroke-width="2.25"
                        stroke-linecap="round"
                        stroke-linejoin="round"
                    />
                </svg>
            </summary>
            <div class="accordion-body">
                <ReadinessDashboard
                    mastery={data.mastery}
                    performance={data.performance}
                    readiness={data.readiness}
                />
            </div>
        </details>

        <details class="accordion">
            <summary>
                <span class="summary-title">General statistics</span>
                <svg
                    class="chevron"
                    viewBox="0 0 24 24"
                    aria-hidden="true"
                    focusable="false"
                >
                    <path
                        d="M6 9l6 6 6-6"
                        fill="none"
                        stroke="currentColor"
                        stroke-width="2.25"
                        stroke-linecap="round"
                        stroke-linejoin="round"
                    />
                </svg>
            </summary>
            <div class="accordion-body">
                <GraphsPage
                    {graphs}
                    initialSearch="deck:current"
                    initialDays={365}
                    controller={RangeBox}
                />
            </div>
        </details>
    </div>
</div>

<style lang="scss">
    // The theme sets canvas/paper texture on `.mcat`; stretch it to fill the
    // embedded webview so the whole surface reads as one calm sheet.
    .stats-page {
        min-height: 100vh;
        width: 100%;
    }

    .stats-shell {
        max-width: 1100px;
        margin: 0 auto;
        padding: clamp(1rem, 4vw, 3rem) clamp(1rem, 4vw, 2.5rem) 4rem;
        display: flex;
        flex-direction: column;
        gap: clamp(1rem, 2.5vw, 1.75rem);
    }

    h1 {
        margin: 0 0 0.25rem;
        font-family: var(--mcat-heading-font);
        font-size: clamp(2rem, 5vw, 3rem);
        line-height: 1.05;
        color: var(--mcat-ink);
    }

    .accordion {
        background: var(--mcat-surface);
        border: 1px solid var(--mcat-border);
        border-radius: var(--mcat-radius-lg);
        box-shadow: var(--mcat-shadow);
        overflow: hidden;
        transition: box-shadow 0.3s var(--mcat-ease);
    }
    .accordion[open] {
        box-shadow: var(--mcat-shadow-lift);
    }

    summary {
        // remove the native disclosure triangle — we draw our own chevron
        list-style: none;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 1rem;
        padding: clamp(1.1rem, 3vw, 1.75rem) clamp(1.25rem, 4vw, 2.25rem);
        user-select: none;
        transition: background-color 0.25s var(--mcat-ease);

        &::-webkit-details-marker {
            display: none;
        }
        &:hover {
            background-color: var(--mcat-surface-2);
        }
        &:focus-visible {
            outline: 3px solid var(--mcat-sky);
            outline-offset: -3px;
        }
    }

    .summary-title {
        font-family: var(--mcat-heading-font);
        font-weight: 600;
        font-optical-sizing: auto;
        letter-spacing: -0.01em;
        font-size: clamp(1.4rem, 3.5vw, 2rem);
        line-height: 1.15;
        color: var(--mcat-ink);
    }

    .chevron {
        flex: 0 0 auto;
        width: clamp(1.5rem, 4vw, 2rem);
        height: clamp(1.5rem, 4vw, 2rem);
        color: var(--mcat-sage-ink);
        transition: transform 0.3s var(--mcat-ease);
    }
    .accordion[open] .chevron {
        transform: rotate(180deg);
    }

    .accordion-body {
        padding: 0 clamp(0.5rem, 3vw, 1.5rem) clamp(1rem, 3vw, 1.75rem);
        border-top: 1px solid var(--mcat-border);
    }

    @media (prefers-reduced-motion: reduce) {
        .accordion,
        .chevron,
        summary {
            transition: none;
        }
    }
</style>
