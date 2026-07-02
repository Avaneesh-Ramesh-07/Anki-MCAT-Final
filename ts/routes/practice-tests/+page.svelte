<!--
Copyright: Ankitects Pty Ltd and contributors
License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
-->
<script lang="ts">
    import { page } from "$app/state";

    import PracticeTests from "./PracticeTests.svelte";

    // `?mode=full-length` scopes this page to the full-length exam; otherwise
    // it lists the topical tests. The Qt toolbar opens the two entry points.
    const fullLength = page.url.searchParams.get("mode") === "full-length";
</script>

<PracticeTests {fullLength} />
