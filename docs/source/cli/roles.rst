Roles and Permissions
========================

SkyShift implements a Role-Based Access Control (RBAC) system to manage access 
permissions within its ecosystem. This RBAC system allows for granular control 
over who can perform actions on specific resources across different namespaces. 
Detailed information about RBAC can be found in the security section 
(details to be added). A "role" in RBAC defines a set of permissions that 
specify the actions allowed on various resources within specified namespaces. 
Users assigned to a role inherit these permissions, aligning their capabilities 
with their organizational roles and responsibilities.

Creating a New Role
-------------------

The ``create role`` command establishes a new role within SkyShift, associating it 
with specified actions, resources, and users.

**Usage:**

.. code-block:: shell

    skyctl create role [OPTIONS] NAME

**Options:**

- ``-a, --action``: Specifies the actions that can be performed by the role.
- ``-r, --resource``: Defines the resources upon which the actions can be performed.
- ``-n, --namespace``: Associates the role with specific namespaces.
- ``-u, --users``: Assigns users to the role.

**Example:**

.. code-block:: shell

    skyctl create role myRole -a create -a delete -r jobs -n development -u user1 -u user2

This command creates a new role named ``myRole`` that allows `create` and `delete` actions on `jobs` resources within the `development` namespace for `user1` and `user2`.

Retrieving Role Information
---------------------------

The ``get roles`` command fetches details about a specific role or all roles if 
none is specified.

**Usage:**

.. code-block:: shell

    skyctl get role [OPTIONS] [NAME]

**Options:**

- ``-w, --watch``: Continuously monitors for changes in role configurations.

**Example:**

.. code-block:: shell

    skyctl get role myRole

Executing this command retrieves information about the role named ``myRole``. 
Omitting the name argument fetches details of all roles.

Deleting a Role
---------------

The ``delete role`` command removes a specified role from SkyShift, revoking the 
associated permissions.

**Usage:**

.. code-block:: shell

    skyctl delete role NAME

**Example:**

.. code-block:: shell

    skyctl delete role myRole

This command deletes the role named ``myRole`` from SkyShift.

.. note:: Deleting a role is irreversible. It's essential to ensure that the role is no longer required before proceeding with deletion.

Understanding Roles in SkyShift
------------------------------

Roles are fundamental to enforcing security and operational policies within SkyShift. They enable administrators to:

- Assign specific permissions to users, ensuring that personnel can only perform actions aligned with their job functions.
- Control access to resources across different namespaces, enhancing security and operational efficiency.
- Streamline the management of permissions as users' roles within the organization change.

Roles, when used effectively, help maintain the integrity and security of the SkyShift environment, ensuring that resources are accessed and managed responsibly.
