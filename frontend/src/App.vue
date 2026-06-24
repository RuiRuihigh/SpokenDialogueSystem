<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { api, fetchAudio } from './config/api'

const token = ref(localStorage.getItem('spoken_token') || '')
const user = ref(JSON.parse(localStorage.getItem('spoken_user') || 'null'))
const authMode = ref('login')
const credentials = ref({ username: '', password: '' })
const authError = ref('')
const busy = ref(false)
const notice = ref('')

const tab = ref('browse')
const search = ref('')
const resources = ref([])
const total = ref(0)
const page = ref(0)
const pageSize = 20
const browseHasMore = ref(true)
const datasetSplits = ref([])
const activeSplit = ref('')
const workspaceElement = ref(null)
const selected = ref(null)
const favorite = ref(false)
const favoriteRows = ref([])
const uploads = ref([])
const playerUrl = ref('')
const audioElement = ref(null)
const uploadForm = ref({ name: '', text: '', metainfo: '' })
const uploadFile = ref(null)
const transcriptMode = ref('manual')
const transcriptionTask = ref(null)

const heading = computed(() => ({ browse: 'Default Audio Dataset', favorites: 'My Favorites', uploads: 'My Uploads', upload: 'Upload Private Audio' }[tab.value]))

function setNotice(message) {
  notice.value = message
  window.setTimeout(() => { if (notice.value === message) notice.value = '' }, 3400)
}

async function authenticate() {
  busy.value = true
  authError.value = ''
  try {
    const data = await api(`/api/user/${authMode.value === 'login' ? 'login' : 'register'}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(credentials.value),
    })
    token.value = data.token
    user.value = data.userInfo
    localStorage.setItem('spoken_token', data.token)
    localStorage.setItem('spoken_user', JSON.stringify(data.userInfo))
    busy.value = false
    await loadBrowse(true)
  } catch (error) {
    authError.value = error.message
  } finally {
    busy.value = false
  }
}

function logout() {
  localStorage.removeItem('spoken_token')
  localStorage.removeItem('spoken_user')
  token.value = ''
  user.value = null
  credentials.value = { username: '', password: '' }
  authMode.value = 'login'
  clearPlayer()
}

async function loadBrowse(reset = true) {
  if (busy.value || (!reset && !browseHasMore.value)) return
  tab.value = 'browse'
  const nextPage = reset ? 1 : page.value + 1
  if (reset) {
    resources.value = []
    total.value = 0
    page.value = 0
    browseHasMore.value = true
  }
  busy.value = true
  try {
    const query = new URLSearchParams({ scope: 'dataset', page: String(nextPage), pageSize: String(pageSize) })
    if (search.value.trim()) query.set('keyword', search.value.trim())
    if (activeSplit.value) query.set('split', activeSplit.value)
    const data = await api(`/api/audio/resources?${query}`, { token: token.value })
    resources.value = reset ? data.list : [...resources.value, ...data.list]
    total.value = data.total
    page.value = nextPage
    browseHasMore.value = data.hasMore
    datasetSplits.value = data.availableSplits || []
  } catch (error) {
    setNotice(error.message)
  } finally {
    busy.value = false
  }
}

function selectSplit(split) {
  activeSplit.value = split
  loadBrowse(true)
}

function handleBrowseScroll(event) {
  const element = event.currentTarget
  if (tab.value === 'browse' && element.scrollTop + element.clientHeight >= element.scrollHeight - 180) {
    loadBrowse(false)
  }
}

async function showDetail(id) {
  busy.value = true
  try {
    selected.value = await api(`/api/audio/resources/${id}`, { token: token.value })
    favorite.value = (await api(`/api/audio/favorites/check?audioId=${id}`, { token: token.value })).isFavorite
    clearPlayer()
  } catch (error) {
    setNotice(error.message)
  } finally {
    busy.value = false
  }
}

async function playSelected() {
  if (!selected.value) return
  busy.value = true
  try {
    clearPlayer()
    playerUrl.value = await fetchAudio(`/api/audio/resources/${selected.value.id}/content`, token.value)
    await new Promise(resolve => requestAnimationFrame(resolve))
    await audioElement.value?.play()
  } catch (error) {
    setNotice(error.message)
  } finally {
    busy.value = false
  }
}

function clearPlayer() {
  if (playerUrl.value) URL.revokeObjectURL(playerUrl.value)
  playerUrl.value = ''
}

async function toggleFavorite() {
  if (!selected.value) return
  try {
    if (favorite.value) {
      await api(`/api/audio/favorites/${selected.value.id}`, { token: token.value, method: 'DELETE' })
      favorite.value = false
      setNotice('Removed from favorites.')
    } else {
      await api('/api/audio/favorites', {
        token: token.value,
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ audioId: selected.value.id }),
      })
      favorite.value = true
      setNotice('Added to favorites.')
    }
  } catch (error) {
    setNotice(error.message)
  }
}

async function deleteSelectedUpload() {
  if (!selected.value || selected.value.sourceType !== 'upload') return
  if (!window.confirm(`Delete “${selected.value.name}”? This cannot be undone.`)) return
  const resourceId = selected.value.id
  busy.value = true
  try {
    await api(`/api/audio/resources/${resourceId}`, { token: token.value, method: 'DELETE' })
    clearPlayer()
    selected.value = null
    if (transcriptionTask.value?.audioResourceId === resourceId) transcriptionTask.value = null
    await loadUploads()
    setNotice('Upload deleted.')
  } catch (error) {
    setNotice(error.message)
  } finally {
    busy.value = false
  }
}

async function generateSelectedTranscript() {
  if (!selected.value || selected.value.sourceType !== 'upload') return
  const resourceId = selected.value.id
  busy.value = true
  try {
    const task = await api(`/api/audio/resources/${resourceId}/transcription`, { token: token.value, method: 'POST' })
    transcriptionTask.value = task
    setNotice('Generating a diarized transcript…')
    await waitForTranscription(task.id, resourceId)
  } catch (error) {
    setNotice(error.message)
  } finally {
    busy.value = false
  }
}

async function loadFavorites() {
  tab.value = 'favorites'
  selected.value = null
  clearPlayer()
  try {
    const data = await api('/api/audio/favorites?page=1&pageSize=50', { token: token.value })
    favoriteRows.value = data.list
  } catch (error) {
    setNotice(error.message)
  }
}

async function loadUploads() {
  tab.value = 'uploads'
  selected.value = null
  clearPlayer()
  try {
    const data = await api('/api/audio/resources?scope=mine&page=1&pageSize=50', { token: token.value })
    uploads.value = data.list
  } catch (error) {
    setNotice(error.message)
  }
}

function openUpload() {
  tab.value = 'upload'
  selected.value = null
  clearPlayer()
}

function chooseFile(event) {
  uploadFile.value = event.target.files?.[0] || null
}

async function submitUpload() {
  if (!uploadFile.value) return setNotice('Please choose an audio file.')
  if (transcriptMode.value === 'manual' && !uploadForm.value.text.trim()) return setNotice('Please provide a transcript.')
  const form = new FormData()
  form.append('file', uploadFile.value)
  form.append('name', uploadForm.value.name)
  form.append('text', transcriptMode.value === 'manual' ? uploadForm.value.text : '')
  form.append('transcription_mode', transcriptMode.value)
  if (uploadForm.value.metainfo.trim()) form.append('metainfo', uploadForm.value.metainfo)
  busy.value = true
  try {
    const resource = await api('/api/audio/uploads', { token: token.value, method: 'POST', body: form })
    uploadForm.value = { name: '', text: '', metainfo: '' }
    uploadFile.value = null
    transcriptMode.value = 'manual'
    selected.value = resource
    favorite.value = false
    await loadUploads()
    await showDetail(resource.id)
    if (resource.transcriptionTask) {
      transcriptionTask.value = resource.transcriptionTask
      setNotice('Upload complete. Generating a diarized transcript…')
      await waitForTranscription(resource.transcriptionTask.id, resource.id)
    } else {
      setNotice('Upload complete. This file is visible only to you.')
    }
  } catch (error) {
    setNotice(error.message)
  } finally {
    busy.value = false
  }
}

async function waitForTranscription(taskId, resourceId) {
  for (let attempt = 0; attempt < 60; attempt += 1) {
    try {
      const task = await api(`/api/audio/resources/transcriptions/${taskId}`, { token: token.value })
      transcriptionTask.value = task
      if (task.status === 'completed') {
        selected.value = await api(`/api/audio/resources/${resourceId}`, { token: token.value })
        await loadUploads()
        await showDetail(resourceId)
        setNotice('Transcript generated with speaker labels.')
        return
      }
      if (task.status === 'failed') {
        setNotice(task.errorMessage || 'Automatic transcription failed.')
        return
      }
    } catch (error) {
      setNotice(error.message)
      return
    }
    await new Promise(resolve => window.setTimeout(resolve, 2000))
  }
  setNotice('Transcription is still running. Open My uploads later to see the result.')
}

onMounted(() => { if (token.value) loadBrowse(true) })
onBeforeUnmount(clearPlayer)
</script>

<template>
  <main v-if="!token" class="auth-shell">
    <section class="auth-card">
      <p class="eyebrow">SPOKEN DIALOGUE SYSTEM</p>
      <h1>Listen to every dialogue</h1>
      <p class="subtle">Explore protected audio, save favorites, and upload your own recordings.</p>
      <form @submit.prevent="authenticate">
        <label>Username<input v-model.trim="credentials.username" minlength="3" required autocomplete="username" /></label>
        <label>Password<input v-model="credentials.password" type="password" minlength="8" required autocomplete="current-password" /></label>
        <p v-if="authError" class="form-error">{{ authError }}</p>
        <button class="primary wide" :disabled="busy">{{ busy ? 'Working…' : authMode === 'login' ? 'Sign in' : 'Create account' }}</button>
      </form>
      <button class="text-button" @click="authMode = authMode === 'login' ? 'register' : 'login'">
        {{ authMode === 'login' ? 'New here? Create an account' : 'Already have an account? Sign in' }}
      </button>
    </section>
  </main>

  <main v-else class="app-shell">
    <aside class="sidebar">
      <div class="brand"><span class="brand-mark">◉</span><span>Spoken<br />Dialogue</span></div>
      <nav>
        <button :class="{ active: tab === 'browse' }" @click="loadBrowse()">Browse audio</button>
        <button :class="{ active: tab === 'favorites' }" @click="loadFavorites()">My favorites</button>
        <button :class="{ active: tab === 'uploads' }" @click="loadUploads()">My uploads</button>
        <button :class="{ active: tab === 'upload' }" @click="openUpload">Upload audio</button>
      </nav>
      <div class="account"><strong>{{ user?.username }}</strong><small>{{ user?.role === 'admin' ? 'Administrator' : 'Signed-in user' }}</small><button class="text-button" @click="logout">Sign out</button></div>
    </aside>

    <section ref="workspaceElement" class="workspace" @scroll="handleBrowseScroll">
      <header><div><p class="eyebrow">AUDIO LIBRARY</p><h1>{{ heading }}</h1></div><span v-if="busy" class="loading">Working…</span></header>
      <p v-if="notice" class="notice">{{ notice }}</p>

      <template v-if="tab === 'browse'">
        <form class="search" @submit.prevent="loadBrowse(true)"><input v-model="search" placeholder="Search audio names or transcripts" /><button class="primary">Search</button></form>
        <div class="split-tabs"><button :class="{ active: !activeSplit }" @click="selectSplit('')">All splits</button><button v-for="split in datasetSplits" :key="split" :class="{ active: activeSplit === split }" @click="selectSplit(split)">{{ split }}</button></div>
        <p class="result-count">{{ total }} resources{{ activeSplit ? ` in ${activeSplit}` : ' across all splits' }}</p>
        <div class="resource-grid"><button v-for="resource in resources" :key="resource.id" class="resource-card" @click="showDetail(resource.id)"><span class="type-tag">Dataset</span><strong>{{ resource.name }}</strong><p>{{ resource.text }}</p><small>{{ Math.round((resource.durationMs || 0) / 1000) }} sec · WAV</small></button></div>
        <p class="infinite-status">{{ busy ? 'Loading audio…' : browseHasMore ? 'Scroll down to load more' : 'You have reached the end.' }}</p>
      </template>

      <template v-else-if="tab === 'favorites' || tab === 'uploads'">
        <div v-if="(tab === 'favorites' ? favoriteRows : uploads).length" class="resource-grid"><button v-for="resource in (tab === 'favorites' ? favoriteRows : uploads)" :key="resource.id" class="resource-card" @click="showDetail(resource.id)"><span class="type-tag">{{ tab === 'favorites' ? 'Favorite' : 'Private' }}</span><strong>{{ resource.name }}</strong><p>{{ resource.text }}</p><small>{{ Math.round((resource.durationMs || 0) / 1000) }} sec · {{ resource.audioFormat?.toUpperCase() }}</small></button></div>
        <div v-else class="empty-state">There are no resources here yet.</div>
      </template>

      <form v-else class="upload-form" @submit.prevent="submitUpload">
        <label>Audio file<input type="file" accept="audio/wav,audio/mpeg,audio/mp4,audio/ogg,.wav,.mp3,.m4a,.ogg" @change="chooseFile" required /></label>
        <label>Display name (optional)<input v-model="uploadForm.name" placeholder="Uses the original filename by default" /></label>
        <fieldset class="transcript-choice"><legend>Transcript source</legend><label><input v-model="transcriptMode" type="radio" value="manual" /> Write it manually</label><label><input v-model="transcriptMode" type="radio" value="asr" /> Generate with OpenAI ASR</label><p v-if="transcriptMode === 'asr'" class="subtle">The system will use gpt-4o-transcribe-diarize and label detected speakers as Person1, Person2, and so on.</p></fieldset>
        <label v-if="transcriptMode === 'manual'">Transcript<textarea v-model="uploadForm.text" required placeholder="Enter the transcript for this audio" /></label>
        <label>Additional JSON metadata (optional)<textarea v-model="uploadForm.metainfo" placeholder='For example: {"fact_summary":"What happened","emotional_summary":"How the speakers feel"}' /><small class="metadata-hint">Use the exact keys <code>fact_summary</code> and <code>emotional_summary</code> to show summaries in the audio details.</small></label>
        <button class="primary" :disabled="busy">{{ transcriptMode === 'asr' ? 'Upload and generate transcript' : 'Upload private audio' }}</button>
      </form>
    </section>

    <aside class="detail-panel">
      <div v-if="selected" class="detail"><div class="detail-top"><span class="type-tag">{{ selected.sourceType === 'upload' ? 'Private upload' : 'Default dataset' }}</span><button class="close" @click="selected = null; clearPlayer()">×</button></div><h2>{{ selected.name }}</h2><p v-if="transcriptionTask && transcriptionTask.audioResourceId === selected.id && transcriptionTask.status !== 'completed'" class="asr-status">Transcript status: {{ transcriptionTask.status }}.</p><p class="detail-text">{{ selected.text || 'Transcript is being generated.' }}</p><p v-if="selected.metainfo?.asr" class="file-meta">Generated by {{ selected.metainfo.asr.model }} · {{ selected.metainfo.asr.speakerLabels?.join(', ') }}</p><div class="summary" v-if="selected.metainfo?.fact_summary"><strong>Factual summary</strong><p>{{ selected.metainfo.fact_summary }}</p><strong>Emotional summary</strong><p>{{ selected.metainfo.emotional_summary }}</p></div><div class="player-actions"><button class="primary" @click="playSelected">Play audio</button><button v-if="selected.sourceType === 'dataset'" class="secondary" @click="toggleFavorite">{{ favorite ? 'Remove favorite' : 'Add favorite' }}</button><template v-else><button class="secondary" @click="generateSelectedTranscript">Generate transcript with ASR</button><button class="danger" @click="deleteSelectedUpload">Delete upload</button></template></div><audio v-if="playerUrl" ref="audioElement" :src="playerUrl" controls class="audio-player"></audio><p class="file-meta">{{ selected.audioFormat?.toUpperCase() }} · {{ Math.round((selected.durationMs || 0) / 1000) }} sec</p></div><div v-else class="detail-empty">Select an audio resource to view its transcript, summaries, and player.</div>
    </aside>
  </main>
</template>
