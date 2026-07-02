<!--
Copyright: Ankitects Pty Ltd and contributors
License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
-->
<script lang="ts">
    import type { PageData } from "./$types";
    import ReadinessDashboard from "./ReadinessDashboard.svelte";

    export let data: PageData;
</script>

<ReadinessDashboard
    mastery={data.mastery}
    performance={data.performance}
    readiness={data.readiness}
/>
