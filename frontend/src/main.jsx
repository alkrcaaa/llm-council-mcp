import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'

// StrictMode is intentionally omitted: App.jsx's SSE streaming reducers mutate
// the previous state object in place (e.g. `lastMsg.stage1Streaming[model] += ...`)
// instead of returning a new one. StrictMode double-invokes state updaters in dev
// to catch exactly this kind of impurity, which for a mutating updater means the
// mutation is applied twice - visible as every streamed word appearing doubled.
// This doesn't affect production builds (StrictMode's double-invoke is dev-only);
// the real fix is making those reducers immutable, tracked separately.
createRoot(document.getElementById('root')).render(<App />)
