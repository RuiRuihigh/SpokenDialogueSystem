<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { api, fetchAudio } from './config/api'
import emotionResultsImage from './assets/landing/emotion-results.png'
import factualResultsImage from './assets/landing/factual-results.png'
import humanEvalImage from './assets/landing/human-eval.png'
import pipelineImage from './assets/landing/pipeline.png'
import taskOverviewImage from './assets/landing/task-overview.png'

const token = ref(localStorage.getItem('spoken_token') || '')
const user = ref(JSON.parse(localStorage.getItem('spoken_user') || 'null'))
const showAuth = ref(false)
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
const speechPlayerUrl = ref('')
const speechAudioElement = ref(null)
const uploadForm = ref({ name: '', text: '', metainfo: '' })
const uploadFile = ref(null)
const transcriptMode = ref('manual')
const transcriptionTask = ref(null)
const speechPrompt = ref('Summarize this audio and describe the main emotion.')
const speechTask = ref(null)
const speechSource = ref('dataset')
const speechSearch = ref('')
const speechResources = ref([])
const selectedSpeechResource = ref(null)
let browseSearchTimer = null
let speechSearchTimer = null

const heading = computed(() => ({ browse: 'Default Audio Dataset', favorites: 'My Favorites', uploads: 'My Uploads', upload: 'Upload Private Audio', speechllm: 'SpeechLLM Workspace' }[tab.value]))

function setNotice(message) {
  notice.value = message
  window.setTimeout(() => { if (notice.value === message) notice.value = '' }, 3400)
}

function scheduleBrowseSearch() {
  if (tab.value !== 'browse') return
  window.clearTimeout(browseSearchTimer)
  browseSearchTimer = window.setTimeout(() => loadBrowse(true), 450)
}

function scheduleSpeechSearch() {
  if (tab.value !== 'speechllm') return
  window.clearTimeout(speechSearchTimer)
  speechSearchTimer = window.setTimeout(() => loadSpeechResources(), 450)
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
  showAuth.value = true
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

function clearSpeechPlayer() {
  if (speechPlayerUrl.value) URL.revokeObjectURL(speechPlayerUrl.value)
  speechPlayerUrl.value = ''
}

async function playSpeechResource() {
  if (!selectedSpeechResource.value) return
  busy.value = true
  try {
    clearSpeechPlayer()
    speechPlayerUrl.value = await fetchAudio(`/api/audio/resources/${selectedSpeechResource.value.id}/content`, token.value)
    await new Promise(resolve => requestAnimationFrame(resolve))
    await speechAudioElement.value?.play()
  } catch (error) {
    setNotice(error.message)
  } finally {
    busy.value = false
  }
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
    if (speechTask.value?.audioResourceId === resourceId) speechTask.value = null
    if (selectedSpeechResource.value?.id === resourceId) selectedSpeechResource.value = null
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

async function runSpeechModel() {
  if (!selectedSpeechResource.value) return setNotice('Please choose an audio resource first.')
  const prompt = speechPrompt.value.trim()
  if (!prompt) return setNotice('Please enter a SpeechLLM prompt.')
  const resourceId = selectedSpeechResource.value.id
  busy.value = true
  try {
    const task = await api(`/api/audio/resources/${resourceId}/speech-tasks`, {
      token: token.value,
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt }),
    })
    speechTask.value = task
    setNotice('SpeechLLM task started.')
    await waitForSpeechTask(task.id)
  } catch (error) {
    setNotice(error.message)
  } finally {
    busy.value = false
  }
}

async function waitForSpeechTask(taskId) {
  for (let attempt = 0; attempt < 120; attempt += 1) {
    try {
      const task = await api(`/api/audio/resources/speech-tasks/${taskId}`, { token: token.value })
      speechTask.value = task
      if (task.status === 'completed') {
        setNotice('SpeechLLM answer is ready.')
        return
      }
      if (task.status === 'failed') {
        setNotice(task.errorMessage || 'SpeechLLM inference failed.')
        return
      }
    } catch (error) {
      setNotice(error.message)
      return
    }
    await new Promise(resolve => window.setTimeout(resolve, 2500))
  }
  setNotice('SpeechLLM is still running. Keep this page open or try again later.')
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

async function openSpeechLLM() {
  tab.value = 'speechllm'
  selected.value = null
  clearPlayer()
  await loadSpeechResources()
}

async function loadSpeechResources() {
  busy.value = true
  try {
    const query = new URLSearchParams({
      scope: speechSource.value === 'mine' ? 'mine' : 'dataset',
      page: '1',
      pageSize: '30',
    })
    if (speechSearch.value.trim()) query.set('keyword', speechSearch.value.trim())
    const data = await api(`/api/audio/resources?${query}`, { token: token.value })
    speechResources.value = data.list
    if (selectedSpeechResource.value && !speechResources.value.some(resource => resource.id === selectedSpeechResource.value.id)) {
      selectedSpeechResource.value = null
    }
  } catch (error) {
    setNotice(error.message)
  } finally {
    busy.value = false
  }
}

function selectSpeechSource(source) {
  speechSource.value = source
  selectedSpeechResource.value = null
  speechTask.value = null
  clearSpeechPlayer()
  loadSpeechResources()
}

function selectSpeechResource(resource) {
  selectedSpeechResource.value = resource
  if (speechTask.value?.audioResourceId !== resource.id) speechTask.value = null
  clearSpeechPlayer()
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

watch(search, scheduleBrowseSearch)
watch(speechSearch, scheduleSpeechSearch)

onMounted(() => { if (token.value) loadBrowse(true) })
onBeforeUnmount(() => {
  window.clearTimeout(browseSearchTimer)
  window.clearTimeout(speechSearchTimer)
  clearPlayer()
  clearSpeechPlayer()
})
</script>

<template>
  <main v-if="!token && !showAuth" class="landing-shell">
    <section class="landing-hero">
      <nav class="landing-nav">
        <div class="landing-brand"><span class="brand-mark">◉</span><span>SpokenDialogueSum</span></div>
        <button class="landing-link" @click="showAuth = true">Access Dataset</button>
      </nav>
      <div class="hero-copy reveal-layer">
        <p class="eyebrow">SPOKEN DIALOGSUM</p>
        <h1>Spoken DialogSum: emotion-rich conversational audio for dialogue summarization.</h1>
        <p class="hero-subtitle">A benchmark for spoken dialogue understanding where vocal delivery, semantic summaries, and grounded paralinguistic cues meet in one dataset.</p>
        <div class="hero-actions">
          <button class="primary landing-cta" @click="showAuth = true">Access Dataset</button>
          <a class="secondary landing-cta" href="#dataset-story">Explore overview</a>
        </div>
        <div class="hero-stats">
          <div><strong>13,460</strong><span>emotion-diverse dialogues</span></div>
          <div><strong>160h</strong><span>expressive multi-speaker audio</span></div>
          <div><strong>2×</strong><span>factual and affect-aware summaries</span></div>
        </div>
      </div>
      <div class="hero-visual">
        <img :src="taskOverviewImage" alt="Spoken dialogue summarization and emotion-rich summarization example" />
      </div>
    </section>

    <section id="dataset-story" class="landing-section landing-dark">
      <div class="section-copy reveal-layer">
        <p class="eyebrow">THE TASK</p>
        <h2>Beyond what happened: why it felt that way.</h2>
        <p>Recent audio-language models can reason over longer spoken conversations, but emotion-aware spoken dialogue summarization still lacks datasets that jointly provide audio, semantic summaries, and grounded paralinguistic cues.</p>
      </div>
      <div class="feature-stat reveal-layer">
        <span>01</span>
        <strong>Factual summary</strong>
        <p>Capture the core event structure of a spoken interaction.</p>
      </div>
      <div class="feature-stat reveal-layer">
        <span>02</span>
        <strong>Emotion extraction</strong>
        <p>Represent speaker-level emotional signals across the conversation.</p>
      </div>
      <div class="feature-stat reveal-layer">
        <span>03</span>
        <strong>Emotion-rich summary</strong>
        <p>Generate summaries that connect emotional states with dialogue events.</p>
      </div>
    </section>

    <section class="landing-section image-story">
      <div class="sticky-copy reveal-layer">
        <p class="eyebrow">DATA CONSTRUCTION</p>
        <h2>A pipeline for realistic spoken dialogue.</h2>
        <p>Starting from DialogSum, scripted daily-life conversations are rewritten into natural spoken-style interactions with paralinguistic annotations, then synthesized as expressive multi-speaker audio aligned with fine-grained supervisory signals.</p>
      </div>
      <figure class="paper-card">
        <img :src="pipelineImage" alt="SpokenDialogueSum construction pipeline" />
        <figcaption>Construction pipeline for spoken dialogue, paralinguistic information, factual summaries, and emotion-rich summaries.</figcaption>
      </figure>
    </section>

    <section class="landing-section metrics-section">
      <div class="section-copy reveal-layer">
        <p class="eyebrow">BENCHMARKS</p>
        <h2>Evaluate both factual and emotion-rich summarization.</h2>
        <p>Spoken DialogSum enables evaluation of zero-shot and adapted audio-language models. Speech-conditioned systems outperform cascaded ASR–LLM baselines on automatic metrics, while adaptation improves human judgments on faithful emotional framing and affective event descriptions.</p>
      </div>
      <div class="metric-grid">
        <figure class="paper-card"><img :src="emotionResultsImage" alt="Emotion-rich summarization performance table" /></figure>
        <figure class="paper-card"><img :src="factualResultsImage" alt="Factual dialogue summarization performance table" /></figure>
        <figure class="paper-card wide"><img :src="humanEvalImage" alt="Human evaluation table for cross-dataset emotion-rich summarization" /></figure>
      </div>
    </section>

    <section class="landing-final">
      <div>
        <p class="eyebrow">READY TO EXPLORE</p>
        <h2>Browse, play, upload, and run SpeechLLM tasks from one protected workspace.</h2>
        <button class="primary landing-cta" @click="showAuth = true">Access Dataset</button>
      </div>
    </section>
  </main>

  <main v-else-if="!token" class="auth-shell">
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
      <button class="text-button" type="button" @click="showAuth = false">Back to dataset overview</button>
    </section>
  </main>

  <main v-else class="app-shell" :class="{ 'has-detail': selected }">
    <aside class="sidebar">
      <div class="brand"><span class="brand-mark">◉</span><span>Spoken<br />Dialogue</span></div>
      <nav>
        <button :class="{ active: tab === 'browse' }" @click="loadBrowse()">Browse audio</button>
        <button :class="{ active: tab === 'favorites' }" @click="loadFavorites()">My favorites</button>
        <button :class="{ active: tab === 'uploads' }" @click="loadUploads()">My uploads</button>
        <button :class="{ active: tab === 'upload' }" @click="openUpload">Upload audio</button>
        <button :class="{ active: tab === 'speechllm' }" @click="openSpeechLLM">SpeechLLM</button>
      </nav>
      <div class="account"><strong>{{ user?.username }}</strong><small>{{ user?.role === 'admin' ? 'Administrator' : 'Signed-in user' }}</small><button class="text-button" @click="logout">Sign out</button></div>
    </aside>

    <section ref="workspaceElement" class="workspace" @scroll="handleBrowseScroll">
      <header><div><p class="eyebrow">AUDIO LIBRARY</p><h1>{{ heading }}</h1></div><span v-if="busy" class="loading">Working…</span></header>
      <p v-if="notice" class="notice">{{ notice }}</p>

      <template v-if="tab === 'browse'">
        <form class="search" @submit.prevent="loadBrowse(true)"><input v-model="search" placeholder="Search audio names or transcripts — updates automatically" /><button class="primary">Search</button></form>
        <div class="split-tabs"><button :class="{ active: !activeSplit }" @click="selectSplit('')">All splits</button><button v-for="split in datasetSplits" :key="split" :class="{ active: activeSplit === split }" @click="selectSplit(split)">{{ split }}</button></div>
        <p class="result-count">{{ total }} resources{{ activeSplit ? ` in ${activeSplit}` : ' across all splits' }}</p>
        <div class="resource-grid"><button v-for="resource in resources" :key="resource.id" class="resource-card" @click="showDetail(resource.id)"><span class="type-tag">Dataset</span><strong>{{ resource.name }}</strong><p>{{ resource.text }}</p><small>{{ Math.round((resource.durationMs || 0) / 1000) }} sec · WAV</small></button></div>
        <p class="infinite-status">{{ busy ? 'Loading audio…' : browseHasMore ? 'Scroll down to load more' : 'You have reached the end.' }}</p>
      </template>

      <template v-else-if="tab === 'favorites' || tab === 'uploads'">
        <div v-if="(tab === 'favorites' ? favoriteRows : uploads).length" class="resource-grid"><button v-for="resource in (tab === 'favorites' ? favoriteRows : uploads)" :key="resource.id" class="resource-card" @click="showDetail(resource.id)"><span class="type-tag">{{ tab === 'favorites' ? 'Favorite' : 'Private' }}</span><strong>{{ resource.name }}</strong><p>{{ resource.text }}</p><small>{{ Math.round((resource.durationMs || 0) / 1000) }} sec · {{ resource.audioFormat?.toUpperCase() }}</small></button></div>
        <div v-else class="empty-state">There are no resources here yet.</div>
      </template>

      <template v-else-if="tab === 'speechllm'">
        <section class="speech-workspace">
          <div class="speech-hero">
            <div>
              <p class="eyebrow">QWEN2-AUDIO WORKBENCH</p>
              <h2>Ask your speech model about any dialogue.</h2>
              <p>Pick an audio resource, provide a single instruction, and run your remote SpeechLLM endpoint with the selected conversation as context.</p>
            </div>
            <div class="model-badge">
              <span class="model-dot"></span>
              <div><strong>RuiRuihigh/qwen2audio</strong><small>Remote HF endpoint</small></div>
            </div>
          </div>

          <div class="speech-console">
            <aside class="speech-library">
              <div class="library-top">
                <strong>Audio source</strong>
                <div class="segmented-control">
                  <button :class="{ active: speechSource === 'dataset' }" @click="selectSpeechSource('dataset')">Dataset</button>
                  <button :class="{ active: speechSource === 'mine' }" @click="selectSpeechSource('mine')">Uploads</button>
                </div>
              </div>
              <form class="speech-search" @submit.prevent="loadSpeechResources">
                <input v-model="speechSearch" placeholder="Search audio…" />
                <button>↵</button>
              </form>
              <div v-if="speechResources.length" class="speech-list">
                <button
                  v-for="resource in speechResources"
                  :key="resource.id"
                  class="speech-row"
                  :class="{ selected: selectedSpeechResource?.id === resource.id }"
                  @click="selectSpeechResource(resource)"
                >
                  <span class="audio-orb">▰</span>
                  <span class="speech-row-body">
                    <strong>{{ resource.name }}</strong>
                    <small>{{ resource.sourceType === 'upload' ? 'Private upload' : 'Dataset audio' }} · {{ Math.round((resource.durationMs || 0) / 1000) }} sec</small>
                  </span>
                </button>
              </div>
              <div v-else class="empty-state compact">No audio matched your search.</div>
            </aside>

            <section class="speech-context">
              <div class="context-header">
                <span class="type-tag">Selected context</span>
                <small v-if="selectedSpeechResource">{{ selectedSpeechResource.audioFormat?.toUpperCase() || 'WAV' }} · {{ Math.round((selectedSpeechResource.durationMs || 0) / 1000) }} sec</small>
              </div>
              <div v-if="selectedSpeechResource" class="context-card">
                <div class="context-title-row">
                  <strong>{{ selectedSpeechResource.name }}</strong>
                </div>
                <div class="context-action-row">
                  <span>{{ selectedSpeechResource.audioFormat?.toUpperCase() || 'WAV' }} · {{ Math.round((selectedSpeechResource.durationMs || 0) / 1000) }} sec</span>
                  <button class="mini-play" @click="playSpeechResource">▶ Play</button>
                </div>
                <audio v-if="speechPlayerUrl" ref="speechAudioElement" :src="speechPlayerUrl" controls class="audio-player"></audio>
                <p>{{ selectedSpeechResource.text }}</p>
              </div>
              <div v-else class="context-empty">
                <span>♪</span>
                <strong>No audio selected</strong>
                <p>Choose a dataset dialogue or one of your uploads to attach it as model context.</p>
              </div>
              <div class="prompt-suggestions">
                <button @click="speechPrompt = 'Generate an emotional summary of each speaker throughout the conversation in one sentence. Use Person1 and Person2 to refer to the speakers.'">Emotion-rich summary</button>
                <button @click="speechPrompt = 'Produce a factual summary of the dialogue in one concise paragraph.'">Factual summary</button>
                <button @click="speechPrompt = 'Describe how each speaker’s emotional state changes over the dialogue.'">Emotion trajectory</button>
              </div>
            </section>

            <section class="speech-chat">
              <div class="chat-window">
                <div class="assistant-message">
                  <span class="assistant-avatar">AI</span>
                  <div>
                    <strong>SpeechLLM</strong>
                    <p>I can summarize, compare speaker emotions, or explain affective events once you attach an audio resource.</p>
                  </div>
                </div>
                <div v-if="speechTask?.answer" class="model-message">
                  <strong>Model answer</strong>
                  <p>{{ speechTask.answer }}</p>
                </div>
                <div v-else-if="speechTask?.status === 'processing'" class="model-message pending">
                  <strong>Thinking through the audio…</strong>
                  <p>The model is reading the selected speech and generating a response.</p>
                </div>
              </div>
              <div class="speech-error-slot">
                <p v-if="speechTask?.status === 'failed' && speechTask.errorMessage" class="form-error">{{ speechTask.errorMessage }}</p>
              </div>
              <div class="composer">
                <textarea v-model="speechPrompt" placeholder="Ask one task about the selected audio…" />
                <div class="composer-footer">
                  <span>{{ selectedSpeechResource ? `Attached: ${selectedSpeechResource.name}` : 'No audio attached' }}</span>
                  <button class="primary" :disabled="busy || !selectedSpeechResource" @click="runSpeechModel">{{ speechTask && speechTask.status === 'processing' ? 'Running…' : 'Run' }}</button>
                </div>
              </div>
            </section>
          </div>
        </section>
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

    <aside v-if="selected" class="detail-panel">
      <div class="detail">
        <div class="detail-top">
          <span class="type-tag">{{ selected.sourceType === 'upload' ? 'Private upload' : 'Default dataset' }}</span>
          <button class="close" @click="selected = null; clearPlayer()">×</button>
        </div>
        <h2>{{ selected.name }}</h2>
        <p v-if="transcriptionTask && transcriptionTask.audioResourceId === selected.id && transcriptionTask.status !== 'completed'" class="asr-status">Transcript status: {{ transcriptionTask.status }}.</p>
        <p class="detail-text">{{ selected.text || 'Transcript is being generated.' }}</p>
        <p v-if="selected.metainfo?.asr" class="file-meta">Generated by {{ selected.metainfo.asr.model }} · {{ selected.metainfo.asr.speakerLabels?.join(', ') }}</p>
        <div class="summary" v-if="selected.metainfo?.fact_summary">
          <strong>Factual summary</strong>
          <p>{{ selected.metainfo.fact_summary }}</p>
          <strong>Emotional summary</strong>
          <p>{{ selected.metainfo.emotional_summary }}</p>
        </div>
        <div class="player-actions">
          <button class="primary" @click="playSelected">Play audio</button>
          <button v-if="selected.sourceType === 'dataset'" class="secondary" @click="toggleFavorite">{{ favorite ? 'Remove favorite' : 'Add favorite' }}</button>
          <template v-else>
            <button class="secondary" @click="generateSelectedTranscript">Generate transcript with ASR</button>
            <button class="danger" @click="deleteSelectedUpload">Delete upload</button>
          </template>
        </div>
        <audio v-if="playerUrl" ref="audioElement" :src="playerUrl" controls class="audio-player"></audio>
        <p class="file-meta">{{ selected.audioFormat?.toUpperCase() }} · {{ Math.round((selected.durationMs || 0) / 1000) }} sec</p>
      </div>
    </aside>
  </main>
</template>
