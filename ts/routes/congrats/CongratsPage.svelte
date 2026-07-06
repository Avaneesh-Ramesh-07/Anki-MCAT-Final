<!--
Copyright: Ankitects Pty Ltd and contributors
License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
-->
<script lang="ts">
    import type { CongratsInfoResponse } from "@generated/anki/scheduler_pb";
    import { congratsInfo } from "@generated/backend";
    import * as tr from "@generated/ftl";
    import { bridgeCommand, bridgeLink } from "@tslib/bridgecommand";

    import Col from "$lib/components/Col.svelte";
    import Container from "$lib/components/Container.svelte";

    import { buildNextLearnMsg } from "./lib";
    import { onMount } from "svelte";

    export let info: CongratsInfoResponse;
    export let refreshPeriodically = true;

    const congrats = tr.schedulingCongratulationsFinished();
    let nextLearnMsg: string;
    $: nextLearnMsg = buildNextLearnMsg(info);
    const today_reviews = tr.schedulingTodayReviewLimitReached();
    const today_new = tr.schedulingTodayNewLimitReached();

    const unburyThem = bridgeLink("unbury", tr.schedulingUnburyThem());
    const buriedMsg = tr.schedulingBuriedCardsFound({ unburyThem });
    const customStudy = bridgeLink("customStudy", tr.schedulingCustomStudy());
    const customStudyMsg = tr.schedulingHowToCustomStudy({
        customStudy,
    });

    onMount(() => {
        if (refreshPeriodically) {
            setInterval(async () => {
                try {
                    info = await congratsInfo({}, { alertOnError: false });
                } catch {
                    console.log("congrats fetch failed");
                }
            }, 60000);
        }
    });
</script>

<Container --gutter-block="1rem" --gutter-inline="2px" breakpoint="sm">
    <Col --col-justify="center">
        <div class="congrats">
            {#if info.bridgeCommandsSupported}
                <button class="garden-back" on:click={() => bridgeCommand("decks")}>
                    ← Water your garden
                </button>
            {/if}

            <h1>{congrats}</h1>

            <p>{nextLearnMsg}</p>

            {#if info.reviewRemaining}
                <p>{today_reviews}</p>
            {/if}

            {#if info.newRemaining}
                <p>{today_new}</p>
            {/if}

            {#if info.bridgeCommandsSupported}
                {#if info.haveSchedBuried || info.haveUserBuried}
                    <p>
                        {@html buriedMsg}
                    </p>
                {/if}

                {#if !info.isFilteredDeck}
                    <p>
                        {@html customStudyMsg}
                    </p>
                {/if}
            {/if}

            {#if info.deckDescription}
                <div class="description">
                    {@html info.deckDescription}
                </div>
            {/if}
        </div>
    </Col>
</Container>

<style lang="scss">
    .congrats {
        margin-top: 2em;
        max-width: 30em;
        font-size: var(--font-size);

        :global(a) {
            color: var(--fg-link);
            text-decoration: none;
        }
    }

    .garden-back {
        display: inline-flex;
        align-items: center;
        gap: 0.4rem;
        margin-bottom: 1.2em;
        padding: 0.5em 1.2em;
        border-radius: 999px;
        border: 1px solid var(--border);
        background: var(--canvas-elevated);
        color: var(--fg);
        font: inherit;
        font-weight: 700;
        cursor: pointer;

        &:hover {
            // pin bg: the global button:hover rule would otherwise wash it white
            background: var(--canvas-elevated);
            border-color: var(--button-primary-bg);
            color: var(--button-primary-bg);
        }
    }

    .description {
        border: 1px solid var(--border);
        padding: 1em;
    }
</style>
