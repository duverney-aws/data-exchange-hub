/**
 * AWS Amplify configuration placeholder.
 * Update these values with your actual Amplify deployment settings.
 */
const amplifyConfig = {
  Auth: {
    Cognito: {
      userPoolId: 'PLACEHOLDER_USER_POOL_ID',
      userPoolClientId: 'PLACEHOLDER_CLIENT_ID',
    },
  },
  API: {
    REST: {
      PharmaAPI: {
        endpoint: 'PLACEHOLDER_API_ENDPOINT',
        region: 'us-east-1',
      },
    },
  },
};

export default amplifyConfig;
