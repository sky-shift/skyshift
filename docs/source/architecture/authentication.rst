Authentication and Authorization in SkyShift
============================================

SkyShift supports AuthN and AuthZ for security for CLI based operations.
The API utilizes a JWT-based authentication and role-based access control
(RBAC) system to ensure secure and efficient access management.
This document details the authentication lifecycle, including user registration
via invitations, login procedures, JWT token management, and authorization
controls through RBAC.

User Registration via Invitation
--------------------------------

User registration in SkyShift is initiated through an invitation system,
where existing users with the necessary permissions can send invitations to
prospective users. This process uses JWTs to secure and specify the parameters
of the invitation.

**Invitation Creation:**

1. An *inviter* creates an invitation by generating a JWT that includes
specified roles and an expiry date. This JWT also encapsulates the inviter's
identifier to trace the origin of the invitation.

2. The inviter sends this JWT to the prospective invitee.

**Registration Process:**

1. The invitee submits the invitation token along with their desired username
and password to the API server.

2. The server validates the JWT by checking its signature, the roles included,
and its expiry against the current time.

3. Upon successful validation, the server hashes the invitee’s password for
secure storage and assigns the roles from the JWT to the invitee's new account.

The JWT used for invitations contains the following claims:

- ``sub``: The prospective user's identifier.
- ``roles``: A list of roles the user will be granted upon successful registration.
- ``iss``: The inviter’s user identifier.
- ``exp``: The token's expiration time to ensure invitations are used within a
limited timeframe.

User Login and JWT Issuance
---------------------------

**Login Process:**

1. Users log in by providing their username and password.
2. The server verifies the credentials against the stored hash.
3. If the credentials are valid, the server issues a JWT that the user will use
for subsequent API requests.

**JWT Structure:**

- **Header**: Specifies JWT and the used algorithm - currently HS512.
- **Payload**: Includes the user’s identifier (`sub`), issued time
(`iat`), and expiration time (`exp`).
- **Signature**: Computed using the secret key to validate the JWT's
integrity.

JWTs are critical for stateless authentication, allowing the server
to verify the token without referencing the user database for each
request.

Role-Based Access Control (RBAC)
-------------------------------

SkyShift implements RBAC to manage access based on user roles
stored within JWTs. Each role defines a set of permissions
associated with resource types across the system.

**Access Decision Process:**

1. When a user makes a request, the server extracts and decodes the
JWT to retrieve user roles.
2. The server checks if any of the user's roles allow the requested
action on the target resource within the specified namespace.
3. Access is granted if a matching role is found; otherwise, a
`401 Unauthorized` response is returned.

**Role Definitions:**

- Roles are defined in the system with specific permissions for
actions such as `read`, `write`, `delete`, and administrative controls
across different API endpoints.

Security and Token Handling
-------------------------------------

**Security TTL:**

- **Token Expiry**: Short-lived tokens reduce the risk of misuse
of stolen tokens. Users must re-authenticate to obtain new tokens periodically.
- **Secret Key Management**: The secret key used to sign the JWTs is
stored securely with a TTL mitigate the risk of unauthorized token creation.

Summary
-------

The auth process in SkyShift uses JWTs for authentication and RBAC for
authorization, we ensure that AuthZ and AuthN are in place to access specific
resources.
