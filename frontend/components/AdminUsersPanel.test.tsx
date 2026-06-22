import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import AdminUsersPanel from "@/components/AdminUsersPanel";
import { systemAuthApi, type AdminUser } from "@/lib/api";

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    systemAuthApi: {
      ...actual.systemAuthApi,
      adminListUsers: vi.fn(),
      adminUpdateUserStatus: vi.fn(),
      adminResetUserPassword: vi.fn(),
    },
  };
});

const users: AdminUser[] = [
  {
    id: 1,
    email: "admin@example.com",
    display_name: "Admin",
    status: "active",
    is_admin: true,
    created_at: "2026-06-22T00:00:00Z",
    updated_at: "2026-06-22T00:00:00Z",
  },
  {
    id: 2,
    email: "member@example.com",
    display_name: "Member",
    status: "active",
    is_admin: false,
    created_at: "2026-06-22T00:00:00Z",
    updated_at: "2026-06-22T00:00:00Z",
  },
];

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("AdminUsersPanel", () => {
  it("lists users and disables a regular user", async () => {
    vi.mocked(systemAuthApi.adminListUsers)
      .mockResolvedValueOnce(users)
      .mockResolvedValueOnce([
        { ...users[0] },
        { ...users[1], status: "inactive" },
      ]);
    vi.mocked(systemAuthApi.adminUpdateUserStatus).mockResolvedValue({
      ...users[1],
      status: "inactive",
    });
    const tester = userEvent.setup();

    render(<AdminUsersPanel currentUserId={1} open onClose={vi.fn()} />);

    expect(await screen.findByText("用户管理")).toBeInTheDocument();
    expect(await screen.findByText("member@example.com")).toBeInTheDocument();

    await tester.click(
      screen.getByRole("button", { name: "禁用 member@example.com" }),
    );

    expect(systemAuthApi.adminUpdateUserStatus).toHaveBeenCalledWith(
      2,
      "inactive",
    );
    await waitFor(() => {
      expect(systemAuthApi.adminListUsers).toHaveBeenCalledTimes(2);
    });
  });

  it("shows the temporary password after resetting a user password", async () => {
    vi.mocked(systemAuthApi.adminListUsers).mockResolvedValue(users);
    vi.mocked(systemAuthApi.adminResetUserPassword).mockResolvedValue({
      user: users[1],
      temporary_password: "temporary-password",
    });
    const tester = userEvent.setup();

    render(<AdminUsersPanel currentUserId={1} open onClose={vi.fn()} />);

    await screen.findByText("member@example.com");
    await tester.click(
      screen.getByRole("button", { name: "重置 member@example.com 的密码" }),
    );

    expect(await screen.findByText("临时密码")).toBeInTheDocument();
    expect(screen.getByText("temporary-password")).toBeInTheDocument();
  });
});
