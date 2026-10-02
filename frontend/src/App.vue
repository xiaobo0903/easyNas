<script setup>
import { NMessageProvider, NDialogProvider, NNotificationProvider, NConfigProvider } from 'naive-ui'
import { computed } from 'vue'

const themeOverrides = {
  common: {
    primaryColor: '#0071e3',
    primaryColorHover: '#0077ed',
    primaryColorPressed: '#005bb5',
    successColor: '#34c759',
    warningColor: '#ff9f0a',
    errorColor: '#ff3b30',
    borderRadius: '8px',
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif"
  }
}
</script>

<template>
  <NConfigProvider :theme-overrides="themeOverrides">
    <NMessageProvider>
      <NDialogProvider>
        <NNotificationProvider>
          <router-view />
        </NNotificationProvider>
      </NDialogProvider>
    </NMessageProvider>
  </NConfigProvider>
</template>
