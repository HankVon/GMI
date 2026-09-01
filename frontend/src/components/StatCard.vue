<template>
  <div class="stat-card ssm-stat-card" :class="accent ? 'has-accent' : ''">
    <div class="sc-num">
      <span class="sc-value">{{ value }}</span>
      <span v-if="suffix" class="sc-suffix">{{ suffix }}</span>
    </div>
    <div class="sc-label">{{ label }}</div>
    <div v-if="sub" class="sc-sub">{{ sub }}</div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  value: string | number
  suffix?: string
  label: string
  sub?: string
  accent?: boolean
}>()
</script>

<style scoped>
.ssm-stat-card {
  background: var(--ssm-card-bg);
  border: 1px solid var(--ssm-border);
  border-radius: var(--ssm-radius);
  padding: 22px 20px;
  box-shadow: var(--ssm-shadow);
  transition: transform 0.25s ease, box-shadow 0.25s ease;
  text-align: left;
}
.ssm-stat-card:hover {
  transform: translateY(-3px);
  box-shadow: var(--ssm-shadow-hover);
}
.sc-num {
  display: flex;
  align-items: baseline;
  gap: 2px;
  font-family: "Georgia", "Times New Roman", serif;
  line-height: 1;
}
.sc-value {
  font-size: 38px;
  font-weight: 700;
  color: var(--ssm-text-main);
}
.sc-suffix {
  font-size: 16px;
  font-weight: 600;
  color: var(--ssm-text-secondary);
}
.has-accent .sc-value {
  color: var(--ssm-primary);
}
.sc-label {
  margin-top: 12px;
  font-size: 14px;
  font-weight: 600;
  color: var(--ssm-text-regular);
}
.sc-sub {
  margin-top: 4px;
  font-size: 12px;
  color: var(--ssm-text-secondary);
  line-height: 1.5;
}
</style>
