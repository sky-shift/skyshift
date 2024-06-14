Users
========================

SkyShift's CLI, `skyctl`, provides an extensive array of commands tailored for user account management. 
Seamlessly integrated with the platform's Role-Based Access Control (RBAC) framework, 
it guarantees stringent security measures for resource access permissions. 
Designed with both simplicity and robust security in mind, `skyctl`` streamlines the user onboarding process, 
effortlessly aligning new users with their respective Roles to ensure immediate productivity without compromising on security. 

Creating a New Account
-------------------

The ``register`` command creates a new account within SkyShift, associating it 
with predefined roles.

**Usage:**

.. code-block:: shell

    skyctl register [OPTIONS] USERNAME PASSWORD

**Options:**

- ``-inv, --invite``: The invite to registering to SkyShift. It should be sent by administrators and contains predefined roles.
- ``--email``: Email address for this account.

**Example:**

.. code-block:: shell

    skyctl register newUser securePassword -inv administrator.invite --email example@example.com

This command creates a new account named ``newUser`` with password ``securePassword``.

.. note:: `USERNAME` should be 4-50 characters long composed of upper or lower case alphabetics, digits and/or _.
.. note:: `PASSWORD` must be 5 or more characters.
.. note:: The invite and associated roles are checked again with sender's access rights at the time of account creation.

Login to an Account
---------------------------

The ``login`` command is used to add or renew the access token for the CLI. 
But it does not change the current active user (see ``switch`` command).

**Usage:**

.. code-block:: shell

    skyctl login USERNAME PASSWORD

**Example:**

.. code-block:: shell

    skyctl login userName securePassword

Executing this command retrieves an access token for the user account and stores it in the local configuration file.

.. note:: If no previous user account exists, this will be used as default active account for future operations. Otherwise the active context remains the same (see ``switch`` command for more detail).

Invite a New User
---------------

The ``invite`` command creates a new invitation to register into SkyShift.

**Usage:**

.. code-block:: shell

    skyctl invite [OPTIONS]

**Options:**

- ``--json``: This flag tells the CLI to output the invitation as field named `invite` in Json format.
- ``-r, --role``: List of roles the new account assumes at creation time. Multiple roles can be specified.

**Example:**

.. code-block:: shell

    skyctl invite --json -r role1 -r role2 -r role3

This returns a Json object with string field invite. When an user creates an account using this invite, 
it will have access right as the specified roles. 

.. note::Only user accounts with the `inviter-role` is able to create invites (by default only the `admin` account after initialization). The granted roles can only have access rights that is a subset of the inviter account.

Revoke an Invitation
---------------

The ``revoke_invite`` command invalidates an existing invitation

**Usage:**

.. code-block:: shell

    skyctl revoke_invite INVITE

**Example:**

.. code-block:: shell

    skyctl revoke_invite previousSentInvite

This revokes the invite and no registeration can be done using it.

.. note:: The invitation could have already been used in which case CLI will display the warning message, but that account will NOT be automatically deleted.

Switch Active Context
---------------

Active context in SkyShift is defined to be the active user account and namespace combined. 
It is the context all provisioning requests are sent with by default.
The ``switch`` updates the local SkyShift config to use the new context.

**Usage:**

.. code-block:: shell

    skyctl switch [OPTIONS]

**Options:**

- ``--user``: The active username to switch to.
- ``-ns, --namespace``: The active namespace to switch to.

**Example:**

.. code-block:: shell

    skyctl switch --user newUser -ns newNamespace

After this command, all future commands uses ``newUser`` and  ``newNamespace``.

.. note:: This command checks if ``newUser`` exists in the local configuration and aborts if not. However, it does NOT check for the validity and active user's access to ``newNamespace``.


Understanding SkyShift Users
------------------------------

Accounts are basic block in identifying different users. Each is tied to a set of 
Roles which then defined the access rights over all the resources. All accounts must be invited by an 
administrator with the proper role. Similar to Kubernetes, users can manage multiple sessions locally 
by switching between active contexts.