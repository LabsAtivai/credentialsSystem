<script setup lang="ts">
defineProps<{
  title: string;
  message: string;
  confirmLabel?: string;
  danger?: boolean;
  loading?: boolean;
}>();

const emit = defineEmits<{ confirm: []; cancel: [] }>();
</script>

<template>
  <div class="modal-overlay" @click.self="emit('cancel')">
    <div class="modal">
      <h2>{{ title }}</h2>
      <p>{{ message }}</p>
      <div class="actions">
        <button type="button" class="btn btn-secondary" @click="emit('cancel')">Cancelar</button>
        <button
          type="button"
          :class="['btn', danger ? 'btn-danger' : 'btn-primary']"
          :disabled="loading"
          @click="emit('confirm')"
        >
          {{ loading ? "Aguarde..." : (confirmLabel ?? "Confirmar") }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
h2 {
  margin-top: 0;
  font-size: 1.05rem;
}
.actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
  margin-top: 1.25rem;
}
</style>
