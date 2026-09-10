# office_leave_management_backend
### Test account visibility

Admins can turn the compact **Testing** switch on or off from the sidebar. It affects only the signed-in admin and defaults to disabled for each admin. The preference is stored in MongoDB in `app_settings` under `_id: "testing-admin:<admin_id>"`. The shared test account IDs remain in `test_user_ids` under `_id: "testing"`; the former global `enabled` field is no longer used. Account selection is not exposed through the sidebar or the testing API.

Configured test accounts and their requests are excluded from request lists, dashboard summaries/counts, balances, and activity logs unless the viewing admin has enabled Testing. Other admins and regular users are unaffected by that switch. Each test account can still see its own data. The admin Employees tab and its employee detail pages always include test data for account management. Toggling Testing refreshes only the current admin's page, without deleting requests or changing login/notice-period rules. There is no polling or window-focus refresh for testing settings.

The authenticated list APIs accept `include_test_users=true` for the admin Employees views; this override is honored only for admins. `GET /api/testing/` reads the signed-in admin's preference (disabled for regular users), while admin-only `PUT /api/testing/` accepts only `{ "enabled": false }` to toggle that admin's visibility. The admin ID comes from authentication. The API does not modify the configured test accounts.
