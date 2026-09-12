<script setup lang="ts">
defineProps<{ online: boolean; pending: number }>()
</script>

<template>
  <span class="badge" :class="{ off: !online, queued: pending > 0 }">
    <template v-if="!online">offline, {{ pending }} wachtend</template>
    <template v-else-if="pending > 0"><span class="tnum">{{ pending }}</span> wachtend</template>
    <template v-else>opgeslagen</template>
  </span>
</template>

<style scoped>
.badge {
  color: var(--text-dim);
  font-size: 15px;
  font-weight: 500;
}
.badge.queued {
  color: var(--queued);
}
.badge.off {
  color: var(--undo);
}
</style>
