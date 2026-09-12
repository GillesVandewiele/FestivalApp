<script setup lang="ts">
import * as echarts from 'echarts'
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = defineProps<{ option: echarts.EChartsCoreOption; height?: number }>()
const el = ref<HTMLDivElement>()
let chart: echarts.ECharts | undefined

function render() {
  if (!el.value) return
  chart ??= echarts.init(el.value, undefined, { renderer: 'svg' })
  chart.setOption(props.option, true)
}

function resize() {
  chart?.resize()
}

onMounted(() => {
  render()
  window.addEventListener('resize', resize)
})
onBeforeUnmount(() => {
  window.removeEventListener('resize', resize)
  chart?.dispose()
})
watch(() => props.option, render, { deep: true })
</script>

<template>
  <div ref="el" class="chart" :style="{ height: `${height ?? 300}px` }" />
</template>

<style scoped>
.chart {
  width: 100%;
}
</style>
