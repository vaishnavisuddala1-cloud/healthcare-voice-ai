(function(){
  const wsState = { socket: null };

  const $ = id => document.getElementById(id);
  const sessionIdInput = $('sessionId');
  const languageSelect = $('language');
  const connectBtn = $('connectBtn');
  const recordBtn = $('recordBtn');
  const messages = $('messages');
  const textInput = $('textInput');
  const sendBtn = $('sendBtn');
  const latency = $('latency');

  let mediaRecorder = null;
  let audioChunks = [];

  function addMessage(text, cls='agent'){
    const li = document.createElement('li');
    li.className = cls;
    li.textContent = text;
    messages.appendChild(li);
    messages.parentElement.scrollTop = messages.parentElement.scrollHeight;
  }

  function connect(){
    if(!sessionIdInput.value || sessionIdInput.value === 'demo-session'){
      sessionIdInput.value = `session-${Date.now()}`;
    }
    const session = sessionIdInput.value;
    const url = `wss://vast-sides-push.loca.lt/ws/${encodeURIComponent(session)}`;
    wsState.socket = new WebSocket(url);

    wsState.socket.onopen = () => {
      addMessage('Connected to server', 'agent');
      connectBtn.disabled = true;
      recordBtn.disabled = false;
    };

    wsState.socket.onmessage = evt => {
      try{
        const payload = JSON.parse(evt.data);
        if(payload.type === 'transcription'){
          addMessage(`Transcription: ${JSON.stringify(payload.data)}`, 'agent');
        } else if(payload.type === 'agent_response' || payload.type === 'outbound_campaign'){
          const msg = payload.data?.message || payload.data;
          addMessage(typeof msg === 'string' ? msg : JSON.stringify(msg), 'agent');
          if(payload.data?.latency_ms) latency.textContent = `Latency: ${payload.data.latency_ms} ms (target <450ms)`;
          if(payload.audio){
            playBase64Audio(payload.audio);
          } else if(payload.data?.message){
            speakResponse(payload.data.message);
          }
        } else {
          addMessage(JSON.stringify(payload), 'agent');
        }
      }catch(e){
        addMessage(evt.data, 'agent');
      }
    };

    wsState.socket.onclose = () => {
      addMessage('Disconnected', 'agent');
      connectBtn.disabled = false;
      recordBtn.disabled = true;
    };

    wsState.socket.onerror = (e) => {
      addMessage('WebSocket error', 'agent');
    };
  }

  connectBtn.addEventListener('click', connect);

  sendBtn.addEventListener('click', () => {
    const text = textInput.value.trim();
    if(!text || !wsState.socket || wsState.socket.readyState !== WebSocket.OPEN) return;
    const payload = { type: 'text', text, language: languageSelect.value };
    wsState.socket.send(JSON.stringify(payload));
    addMessage(text, 'user');
    textInput.value = '';
  });

  textInput.addEventListener('keydown', (e) => { if(e.key === 'Enter') sendBtn.click(); });

  // Audio recording using MediaRecorder
  recordBtn.addEventListener('click', async () => {
    if(!mediaRecorder || mediaRecorder.state === 'inactive'){
      // start recording
      try{
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(stream);
        audioChunks = [];
        mediaRecorder.ondataavailable = e => audioChunks.push(e.data);
        mediaRecorder.onstop = async () => {
          const blob = new Blob(audioChunks, { type: 'audio/webm' });
          try {
            const wavBase64 = await blobToWavBase64(blob);
            const payload = { type: 'audio', data: wavBase64, language: languageSelect.value };
            if(wsState.socket && wsState.socket.readyState === WebSocket.OPEN){
              wsState.socket.send(JSON.stringify(payload));
              addMessage('[audio sent as WAV]', 'user');
            } else {
              addMessage('WebSocket not connected', 'agent');
            }
          } catch (e) {
            addMessage('Audio conversion failed', 'agent');
          }
        };
        mediaRecorder.start();
        recordBtn.textContent = 'Stop Recording';
      }catch(e){
        addMessage('Microphone access denied or not supported', 'agent');
      }
    } else {
      // stop
      mediaRecorder.stop();
      recordBtn.textContent = 'Start Recording';
    }
  });

  function arrayBufferToBase64(buffer){
    let binary = '';
    const bytes = new Uint8Array(buffer);
    const len = bytes.byteLength;
    for (let i = 0; i < len; i++){
      binary += String.fromCharCode(bytes[i]);
    }
    return btoa(binary);
  }

  async function blobToWavBase64(blob){
    const arrayBuffer = await blob.arrayBuffer();
    const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    const decoded = await audioCtx.decodeAudioData(arrayBuffer);
    if (audioCtx.close) {
      audioCtx.close();
    }
    const wavBuffer = encodeWAV(decoded);
    return arrayBufferToBase64(wavBuffer);
  }

  function encodeWAV(audioBuffer){
    const numChannels = audioBuffer.numberOfChannels;
    const sampleRate = audioBuffer.sampleRate;
    const samples = audioBuffer.length;
    let interleaved;

    if(numChannels === 2){
      const left = audioBuffer.getChannelData(0);
      const right = audioBuffer.getChannelData(1);
      interleaved = interleave(left, right);
    } else {
      interleaved = audioBuffer.getChannelData(0);
    }

    const buffer = new ArrayBuffer(44 + interleaved.length * 2);
    const view = new DataView(buffer);

    /* RIFF identifier */
    writeString(view, 0, 'RIFF');
    /* file length */
    view.setUint32(4, 36 + interleaved.length * 2, true);
    /* RIFF type */
    writeString(view, 8, 'WAVE');
    /* format chunk identifier */
    writeString(view, 12, 'fmt ');
    /* format chunk length */
    view.setUint32(16, 16, true);
    /* sample format (raw) */
    view.setUint16(20, 1, true);
    /* channel count */
    view.setUint16(22, numChannels, true);
    /* sample rate */
    view.setUint32(24, sampleRate, true);
    /* byte rate (sample rate * block align) */
    view.setUint32(28, sampleRate * numChannels * 2, true);
    /* block align (channel count * bytes/sample) */
    view.setUint16(32, numChannels * 2, true);
    /* bits per sample */
    view.setUint16(34, 16, true);
    /* data chunk identifier */
    writeString(view, 36, 'data');
    /* data chunk length */
    view.setUint32(40, interleaved.length * 2, true);

    // write the PCM samples
    let offset = 44;
    for (let i = 0; i < interleaved.length; i++, offset += 2) {
      const s = Math.max(-1, Math.min(1, interleaved[i]));
      view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true);
    }

    return buffer;
  }

  function interleave(left, right){
    const length = left.length + right.length;
    const result = new Float32Array(length);
    let index = 0;
    let inputIndex = 0;
    while (index < length) {
      result[index++] = left[inputIndex];
      result[index++] = right[inputIndex];
      inputIndex++;
    }
    return result;
  }

  function writeString(view, offset, string){
    for (let i = 0; i < string.length; i++){
      view.setUint8(offset + i, string.charCodeAt(i));
    }
  }

  function playBase64Audio(b64){
    const audio = new Audio(`data:audio/wav;base64,${b64}`);
    audio.play();
  }

  async function speakResponse(text){
    try{
      const response = await fetch('/api/tts/synthesize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, language: languageSelect.value }),
      });
      if (!response.ok) return;
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      audio.play();
    } catch (e) {
      console.warn('TTS audio playback failed', e);
    }
  }

  // Auto-connect for convenience
  window.addEventListener('load', () => {});
})();