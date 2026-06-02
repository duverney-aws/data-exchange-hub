import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { Amplify } from 'aws-amplify';
import { fetchAuthSession } from 'aws-amplify/auth';
import '@cloudscape-design/global-styles/index.css';
import App from './App';
import { AuthProvider } from './context/AuthContext';
import { setTokenProvider } from './services/api';

setTokenProvider(async () => {
  try {
    const session = await fetchAuthSession();
    return session.tokens?.idToken?.toString() ?? null;
  } catch { return null; }
});

Amplify.configure({
  Auth: {
    Cognito: {
      userPoolId: import.meta.env.VITE_COGNITO_USER_POOL_ID ?? '',
      userPoolClientId: import.meta.env.VITE_COGNITO_CLIENT_ID ?? '',
      loginWith: {
        oauth: {
          domain: 'pharma-data-exchange-portal.auth.us-east-1.amazoncognito.com',
          scopes: ['openid', 'email', 'profile'],
          redirectSignIn: [
            'https://main.d28qy16znlocxk.amplifyapp.com/',
            'http://localhost:3000/',
          ],
          redirectSignOut: [
            'https://main.d28qy16znlocxk.amplifyapp.com/',
            'http://localhost:3000/',
          ],
          responseType: 'code',
        },
      },
    },
  },
});

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <App />
      </AuthProvider>
    </BrowserRouter>
  </React.StrictMode>,
);
