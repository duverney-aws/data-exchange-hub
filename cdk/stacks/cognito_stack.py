"""
Cognito Stack

User Pool with two groups:
  - merck-admins : Merck Data Platform Admins
  - cmo-users    : CMO Representatives

Hosted UI enabled for login/signup.
"""
from aws_cdk import (
    Stack,
    RemovalPolicy,
    CfnOutput,
    aws_cognito as cognito,
)
from constructs import Construct


class CognitoStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.user_pool = cognito.UserPool(
            self, "UserPool",
            user_pool_name="pharma-data-exchange-users",
            self_sign_up_enabled=False,          # only admins create users
            sign_in_aliases=cognito.SignInAliases(email=True),
            auto_verify=cognito.AutoVerifiedAttrs(email=True),
            standard_attributes=cognito.StandardAttributes(
                email=cognito.StandardAttribute(required=True, mutable=True),
                given_name=cognito.StandardAttribute(required=True, mutable=True),
                family_name=cognito.StandardAttribute(required=True, mutable=True),
            ),
            custom_attributes={
                "organization": cognito.StringAttribute(mutable=True),
            },
            password_policy=cognito.PasswordPolicy(
                min_length=8,
                require_uppercase=True,
                require_digits=True,
                require_symbols=False,
            ),
            removal_policy=RemovalPolicy.DESTROY,
        )

        # Groups
        cognito.CfnUserPoolGroup(
            self, "MerckAdminsGroup",
            user_pool_id=self.user_pool.user_pool_id,
            group_name="merck-admins",
            description="Merck Data Platform Administrators",
        )
        cognito.CfnUserPoolGroup(
            self, "CMOUsersGroup",
            user_pool_id=self.user_pool.user_pool_id,
            group_name="cmo-users",
            description="CMO Representatives",
        )

        # Hosted UI domain
        self.user_pool.add_domain(
            "HostedUIDomain",
            cognito_domain=cognito.CognitoDomainOptions(
                domain_prefix="pharma-data-exchange-portal",
            ),
        )

        # App client
        self.app_client = self.user_pool.add_client(
            "PortalClient",
            user_pool_client_name="pharma-portal",
            auth_flows=cognito.AuthFlow(
                user_srp=True,
                user_password=True,
            ),
            o_auth=cognito.OAuthSettings(
                flows=cognito.OAuthFlows(authorization_code_grant=True),
                scopes=[
                    cognito.OAuthScope.OPENID,
                    cognito.OAuthScope.EMAIL,
                    cognito.OAuthScope.PROFILE,
                ],
                callback_urls=[
                    "https://main.d28qy16znlocxk.amplifyapp.com/",
                    "http://localhost:3000/",
                ],
                logout_urls=[
                    "https://main.d28qy16znlocxk.amplifyapp.com/",
                    "http://localhost:3000/",
                ],
            ),
            generate_secret=False,
            prevent_user_existence_errors=True,
        )

        CfnOutput(self, "UserPoolId", value=self.user_pool.user_pool_id)
        CfnOutput(self, "UserPoolClientId", value=self.app_client.user_pool_client_id)
        CfnOutput(self, "HostedUIDomain", value="pharma-data-exchange-portal.auth.us-east-1.amazoncognito.com")
