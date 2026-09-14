<script setup>
import { computed } from 'vue'

const props = defineProps({
  modelValue: { type: Object, default: null }
})

const visible = computed(() => !!props.modelValue)
const text = computed(() => (props.modelValue && props.modelValue.text) || '')
</script>

<template>
  <div v-if="visible" class="toast">{{ text }}</div>
</template>

