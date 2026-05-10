import { isBareIntentMetadataJson } from './intentMeta.js'
import { parseOpenRouterModel } from './openRouterModel.js'

export const initialState = {
  streaming: false,
  networkError: null,
  modelRaw: '',
  codeSource: '',
  openrouterModel: null,
  /** Last non-empty slug from SSE; kept across RUN_START so the bar can show it until the next run reports one. */
  lastOpenrouterModel: null,
  sandboxResult: null,
  repair: null,
  done: null,
  /** @type {'conversational' | 'data' | null} */
  userIntent: null,
  /** @type {string[]} */
  activityLog: [],
  steps: {
    model: 'pending',
    sandbox: 'pending',
    done: 'pending',
  },
}

function appendActivityLog(activityLog, line) {
  const msg = typeof line === 'string' ? line.trim() : ''
  if (!msg || isBareIntentMetadataJson(msg)) return activityLog
  return [...activityLog, msg].slice(-20)
}

function openrouterLogLine(model) {
  return typeof model === 'string' && model.trim()
    ? `OpenRouter model: ${model.trim()}`
    : ''
}

/**
 * @param {{ openrouterModel: string | null, lastOpenrouterModel: string | null }} state
 * @param {unknown} payload
 */
function mergeOpenrouterFromPayload(state, payload) {
  const parsed = parseOpenRouterModel(payload)
  return {
    openrouterModel: parsed ?? state.openrouterModel,
    lastOpenrouterModel: parsed ? parsed : state.lastOpenrouterModel,
  }
}

export function reducer(state, action) {
  switch (action.type) {
    case 'RUN_START':
      return {
        ...initialState,
        // Keep the last useful result visible until this run produces a replacement.
        sandboxResult: state.sandboxResult,
        lastOpenrouterModel: state.lastOpenrouterModel ?? state.openrouterModel,
        streaming: true,
        steps: {
          model: 'active',
          sandbox: 'pending',
          done: 'pending',
        },
      }

    case 'RESET_SESSION':
      return {
        ...initialState,
      }

    case 'SSE_STATUS': {
      const { step, message, intent, error } = action.payload
      const om = mergeOpenrouterFromPayload(state, action.payload)
      const resolvedSlug = parseOpenRouterModel(action.payload)
      const statusMessage =
        typeof message === 'string' && message.trim() ? message.trim() : ''
      if (error === true) {
        const nextLog = appendActivityLog(state.activityLog, statusMessage)
        return {
          ...state,
          ...om,
          networkError: statusMessage || state.networkError,
          activityLog: nextLog,
          steps: {
            ...state.steps,
            model: step === 'model' ? 'failed' : state.steps.model,
          },
        }
      }
      if (step === 'intent') {
        const nextIntent =
          intent === 'conversational' || intent === 'data' ? intent : state.userIntent
        let logLine = ''
        const msgTrim = typeof message === 'string' ? message.trim() : ''
        if (msgTrim && !isBareIntentMetadataJson(msgTrim)) {
          logLine = msgTrim
          if (nextIntent === 'conversational') {
            logLine += ' · Quick reply (no sandbox)'
          } else if (nextIntent === 'data') {
            logLine += ' · Data or tools may run'
          }
        } else if (nextIntent === 'conversational') {
          logLine = 'Quick reply — no sandbox run.'
        } else if (nextIntent === 'data') {
          logLine = 'This request may use data or a sandbox run.'
        }
        const nextLog = appendActivityLog(state.activityLog, logLine)
        const sandboxStep =
          nextIntent === 'conversational'
            ? 'skipped'
            : state.steps.sandbox === 'skipped'
              ? 'pending'
              : state.steps.sandbox
        return {
          ...state,
          ...om,
          userIntent: nextIntent ?? state.userIntent,
          activityLog: nextLog,
          steps: {
            ...state.steps,
            sandbox: sandboxStep,
          },
        }
      }
      if (step === 'model') {
        const nextLog = appendActivityLog(
          appendActivityLog(state.activityLog, message),
          openrouterLogLine(resolvedSlug ?? om.openrouterModel),
        )
        return {
          ...state,
          ...om,
          activityLog: nextLog,
          steps: {
            ...state.steps,
            model: 'active',
            sandbox:
              state.userIntent === 'conversational'
                ? 'skipped'
                : state.steps.sandbox === 'done'
                  ? 'done'
                  : state.steps.sandbox,
            done: 'pending',
          },
        }
      }
      if (step === 'sandbox') {
        const nextLog = appendActivityLog(state.activityLog, message)
        if (state.userIntent === 'conversational') {
          return {
            ...state,
            ...om,
            activityLog: nextLog,
            steps: {
              ...state.steps,
              model: 'done',
              sandbox: 'skipped',
              done: 'pending',
            },
          }
        }
        return {
          ...state,
          ...om,
          activityLog: nextLog,
          steps: {
            model: 'done',
            sandbox: 'active',
            done: 'pending',
          },
        }
      }
      return state
    }

    case 'SSE_MODEL_OUTPUT': {
      const { raw } = action.payload
      const chunk = raw ?? ''
      const om = mergeOpenrouterFromPayload(state, action.payload)
      return {
        ...state,
        ...om,
        modelRaw: state.modelRaw ? state.modelRaw + chunk : chunk,
      }
    }

    case 'SSE_CODE':
      return {
        ...state,
        codeSource: action.payload.source ?? '',
        steps: {
          ...state.steps,
          model: 'done',
        },
      }

    case 'SSE_SANDBOX_RESULT': {
      const r = action.payload
      const ok = Number(r.exit_code) === 0
      const sid = r.sandbox_id ?? ''
      const isConversationalMarker = sid === 'intent:conversational'
      const sandboxStep = isConversationalMarker
        ? ok
          ? 'skipped'
          : 'failed'
        : ok
          ? 'done'
          : 'failed'
      return {
        ...state,
        sandboxResult: r,
        steps: {
          ...state.steps,
          model: 'done',
          sandbox: sandboxStep,
        },
      }
    }

    case 'SSE_REPAIR': {
      const { attempt, max, error } = action.payload
      return {
        ...state,
        modelRaw: '',
        codeSource: '',
        repair: {
          attempt,
          max,
          error: error ?? '',
          variant: 'amber',
          mode: 'repair',
        },
        steps: {
          model: 'pending',
          sandbox: 'retrying',
          done: 'pending',
        },
      }
    }

    case 'SSE_DONE': {
      const { success, attempts, intent } = action.payload
      const om = mergeOpenrouterFromPayload(state, action.payload)
      const sandboxStep = success ? 'done' : 'failed'
      const doneStep = success ? 'done' : 'failed'
      let repair = null
      if (!success) {
        if (state.repair) {
          repair = { ...state.repair, variant: 'red', mode: 'repair' }
        } else if (attempts >= 3) {
          repair = {
            attempt: attempts,
            max: 3,
            error: 'Failed after 3 attempts',
            variant: 'red',
            mode: 'terminal',
          }
        } else {
          repair = {
            attempt: attempts,
            max: 3,
            error: 'Pipeline failed',
            variant: 'red',
            mode: 'terminal',
          }
        }
      }
      const resolvedIntent =
        intent === 'conversational' || intent === 'data'
          ? intent
          : state.userIntent
      return {
        ...state,
        streaming: false,
        ...om,
        done: { success, attempts, intent: resolvedIntent },
        repair,
        steps: {
          model: 'done',
          sandbox:
            state.userIntent === 'conversational' && success
              ? 'skipped'
              : sandboxStep,
          done: doneStep,
        },
      }
    }

    case 'SSE_ERROR':
      return {
        ...state,
        streaming: false,
        networkError: action.payload.message ?? 'Request failed',
        steps: {
          model: state.steps.model === 'pending' ? 'failed' : state.steps.model,
          sandbox:
            state.steps.sandbox === 'pending' ||
            state.steps.sandbox === 'active' ||
            state.steps.sandbox === 'retrying'
              ? 'failed'
              : state.steps.sandbox,
          done: 'failed',
        },
      }

    case 'RUN_CANCELLED':
      return {
        ...state,
        streaming: false,
        steps: {
          model: state.steps.model === 'active' ? 'failed' : state.steps.model,
          sandbox:
            state.steps.sandbox === 'active' || state.steps.sandbox === 'retrying'
              ? 'failed'
              : state.steps.sandbox,
          done: state.done ? state.steps.done : 'failed',
        },
      }

    default:
      return state
  }
}
