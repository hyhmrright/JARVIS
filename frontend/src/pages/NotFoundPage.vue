<template>
  <div class="min-h-screen bg-gray-950 flex items-center justify-center">
    <div class="text-center">
      <h1 class="text-6xl font-bold text-gray-400 mb-4">404</h1>
      <p class="text-xl text-gray-500 mb-8">{{ $t('notFound.message', 'Page not found') }}</p>
      <router-link
        to="/"
        class="px-6 py-3 bg-blue-600 hover:bg-blue-500 text-white rounded-lg transition-colors"
      >
        {{ $t('notFound.backHome', 'Back to Home') }}
      </router-link>
    </div>
  </div>
</template>
