Use Case: RBAC for an Organization
=======================================================================

To demonstrate the access management provided by SkyShift, we will set up various RBAC policies
for an organization and assign roles to users. For this guide, let's assume we have three distinct roles in the organization: **Developers**, **Admins**, and **Operators**.

We will define the permissions associated with each role, invite users, and manage their access
using both CLI commands and YAML configurations.

We can define the following roles and associated permissions:

- **Admin**: Has full control over the SkyShift ecosystem, including user and role management.
- **Developer**: Can create, update, and delete services within specific namespaces.
- **Operator**: Can only monitor services but cannot create or delete them.


Step 1: Inviting Users
~~~~~~~~~~~~~~~~~~~~~~

Before defining the roles, we start by inviting users and assigning their respective roles.
Let's go through the steps to send invitations, registering and logging in.

**Invite the Admin User**

- **Command**:

  .. code-block:: shell

    skyctl invite --role=admin

- **Example Output**:

  .. code-block:: shell

    ⠙ Creating invite
    Invitation created successfully. Invite: <admin_invite_token>
    ✔ Creating invite completed successfully.

- **Register the Admin User**:

  .. code-block:: shell

    skyctl register admin_user1 myPassword --invite <admin_invite_token>

- **Login as Admin User**:

  .. code-block:: shell

    skyctl login admin_user1 myPassword

The admin_user1 can now perform privileged actions

**Invite the Developer Users**

- **Command**:

  .. code-block:: shell

    skyctl invite --role=developer

- **Example Output**:

  .. code-block:: shell

    ⠙ Creating invite
    Invitation created successfully. Invite: <developer_invite_token>
    ✔ Creating invite completed successfully.

- **Register the Developer Users**:

  .. code-block:: shell

    skyctl register dev_user1 myPassword --invite <developer_invite_token>
    skyctl register dev_user2 myPassword --invite <developer_invite_token>

- **Login as Developer User**:

  .. code-block:: shell

    skyctl login dev_user1 myPassword


**Invite the Operator Users**

- **Command**:

  .. code-block:: shell

    skyctl invite --role=operator

- **Example Output**:

  .. code-block:: shell

    ⠙ Creating invite
    Invitation created successfully. Invite: <operator_invite_token>
    ✔ Creating invite completed successfully.

- **Register the Operator Users**:

  .. code-block:: shell

    skyctl register ops_user1 myPassword --invite <operator_invite_token>
    skyctl register ops_user2 myPassword --invite <operator_invite_token>

- **Login as Operator User**:

  .. code-block:: shell

    skyctl login ops_user1 myPassword


Step 2: Defining and Applying Roles
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Now that users are invited and registered, we can define the roles and assign specific permissions.
Role creation can be done either by CLI or applying YAML files, we will demonstrate both.
(The associated YAML files are available in the authentication example folder)

**Developer Role**:

- **CLI Command**:

  .. code-block:: shell

    skyctl create role developer --action=create --action=update --action=delete --resource=services --namespace=dev --namespace=staging --users=dev_user1 --users=dev_user2

- **YAML Configuration**:

  .. code-block:: yaml

    kind: Role
    metadata:
      name: developer
      namespaces:
        - dev
        - staging
    rules:
      - name: service-management
        resources:
          - services
        actions:
          - create
          - update
          - delete
    users:
      - dev_user1
      - dev_user2

  Apply this YAML file with the following command:

  .. code-block:: shell

    skyctl apply -f <path_to_developer_role_yaml>

  .. code-block:: shell

    ⠙ Creating role
    Created role developer.
    ✔ Creating role completed successfully.

Congrats, you have successfully created a `developer` role that grants `dev_user1` and `dev_user2`
permissions to create, update, and delete `services` in the `dev` and `staging` namespaces.


**Admin Role**:

- **CLI Command**:

  .. code-block:: shell

    skyctl create role admin --action=create --action=update --action=delete --action=get --action=list --resource=services --resource=clusters --resource=user --users=admin_user1

- **YAML Configuration**:

  .. code-block:: yaml

    kind: Role
    metadata:
      name: admin
    rules:
      - name: full-access
        resources:
          - services
          - clusters
          - users
        actions:
          - create
          - update
          - delete
          - get
          - list
          - watch
          - restart
    users:
      - admin_user1

  Apply this YAML file with the following command:

  .. code-block:: shell

    skyctl apply -f <path_to_admin_role_yaml>

  .. code-block:: shell

    ⠙ Applying configuration
    Created role admin.
    ✔ Applying configuration completed successfully.

This creates an `admin` role that grants `admin_user1` full access to all actions on
`services`, `clusters`, and `users` within SkyShift.

**Operator Role**:

- **CLI Command**:

  .. code-block:: shell

    skyctl create role operator --action=get --action=list --resource=services --namespace=production --users=ops_user1 --users=ops_user2

- **YAML Configuration**:

  .. code-block:: yaml

    kind: Role
    metadata:
      name: operator
      namespaces:
        - production
    rules:
      - name: service-operations
        resources:
          - services
        actions:
          - get
          - list
    users:
      - ops_user1
      - ops_user2

  Apply this YAML file with the following command:

  .. code-block:: shell

    skyctl apply -f <path_to_operator_role_yaml>

  .. code-block:: shell

    ⠙ Creating role
    Created role operator.
    ✔ Creating role completed successfully.

This creates an `operator` role that grants `ops_user1` and `ops_user2`
permissions to get and list `services` in the `production` namespace, without the ability to create or delete them.


Step 3: Verifying Permissions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

After the users have been registered and logged in, we can verify their permissions by attempting various actions.

Let's login as a developer and perform some actions.

- **Allowed**: Create a new service in the `dev` namespace.

  .. code-block:: shell

    > skyctl create service my-dev-service --namespace=dev --service_type=ClusterIP --ports 80 8080

  .. code-block:: shell

    ⠙ Creating service
    Created service my-dev-service.
    ✔ Creating service completed successfully.

- **Denied**: Delete the admin role.

  .. code-block:: shell

    > skyctl delete role admin
    ✖ Deleting role failed.
    Error:
    Failed to delete role: (401, 'Unauthorized access. User does not have the required role.')
