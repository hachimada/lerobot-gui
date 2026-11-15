import { useState } from 'react';
import { Rich } from '../lib/rich';
import { useStore } from '../lib/store';
import { app, hfAccount, loadAccounts } from '../state/app';
import { Alerts } from './Alerts';
import { Card } from './Card';
import { Icon } from './Icon';

const PLACEHOLDER = 'Access token (hf_…)';
const USES =
  'Push to Hub in Record, Rollout and Train, and private or gated datasets and models. When logged in, repo ids are offered with your account and its organizations. The token is kept where `hf auth login` keeps it; the GUI never shows it again.';

/** The Hugging Face login: who is logged in, log in with an access token, log out. */
export function HfAccountCard() {
  const accounts = useStore(app, (s) => s.accounts);
  const busy = useStore(app, (s) => s.accountsBusy);
  const [secret, setSecret] = useState('');
  const st = accounts?.hf;
  const login = () => {
    void hfAccount(secret);
    setSecret('');
  };
  const pill = !accounts ? (
    <span className="pill">Checking…</span>
  ) : st?.logged_in ? (
    <span className="pill ok">Logged in</span>
  ) : (
    <span className="pill fail">Not logged in</span>
  );
  let body;
  if (!accounts) body = <div className="muted">Checking the saved login…</div>;
  else if (st?.logged_in) {
    body = (
      <>
        <div style={{ fontSize: 14 }}>
          {st.user ? (
            <>
              Logged in as <b className="mono">{st.user}</b>
            </>
          ) : (
            'Logged in'
          )}
        </div>
        {st.error && <Alerts items={[{ level: 'warn', text: st.error }]} />}
        {!!st.orgs?.length && <div className="muted tiny">Organizations: {st.orgs.join(', ')}</div>}
        {st.token_role && (
          <div className="muted tiny">
            Token: {st.token_name || 'unnamed'} ({st.token_role}
            {st.token_role === 'read' ? ': cannot push' : ''})
          </div>
        )}
        {st.where && (
          <div className="muted tiny">
            <Rich text={`Saved in \`${st.where}\`.`} />
          </div>
        )}
        <div className="run-bar" style={{ marginTop: 12 }}>
          <button className="btn ghost small" type="button" disabled={busy} onClick={() => void loadAccounts(true)}>
            <Icon name="refresh" />
            Check again
          </button>
          <button
            className="btn danger small"
            type="button"
            disabled={busy}
            onClick={() => {
              const question = 'Log out of Hugging Face? This deletes the saved tokens from this computer, as `hf auth logout` does.';
              if (window.confirm(question)) void hfAccount(null);
            }}
          >
            Log out
          </button>
        </div>
      </>
    );
  } else {
    body = (
      <>
        {st?.error && <Alerts items={[{ level: 'warn', text: st.error }]} />}
        <div className="muted" style={{ fontSize: 12.5, marginBottom: 8 }}>
          Paste an access token. To push datasets and models it needs write access.
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <input
            className="input mono"
            type="password"
            aria-label={`Hugging Face ${PLACEHOLDER}`}
            autoComplete="off"
            spellCheck={false}
            placeholder={PLACEHOLDER}
            value={secret}
            onChange={(e) => setSecret(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && login()}
          />
          <button className="btn primary small" type="button" disabled={busy} style={{ height: 36 }} onClick={login}>
            {busy ? 'Checking…' : 'Log in'}
          </button>
        </div>
        <div className="muted tiny" style={{ marginTop: 8 }}>
          <a href="https://huggingface.co/settings/tokens" target="_blank" rel="noopener noreferrer">
            Create a token on huggingface.co
          </a>
          {st?.where ? `  ·  saved to ${st.where}` : ''}
        </div>
      </>
    );
  }
  return (
    <Card title="Account" extra={pill}>
      <div className="card-body" style={{ padding: '14px 16px' }}>
        {body}
        <div className="muted tiny" style={{ marginTop: 10 }}>
          <Rich text={USES} />
        </div>
      </div>
    </Card>
  );
}
