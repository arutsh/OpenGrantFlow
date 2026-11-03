import { getUserIdFromToken } from "@/utils/token";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/context/AuthContext";
import gatewayApi from "./gatewayApi";

export const loginUser = async (email: string, password: string) => {
  const { data } = await gatewayApi.post("/auth/login", { email, password });
  return data;
};

export const registerUser = async (
  email: string,
  password: string,
  consentDataProcessing: boolean,
  consentMarketing: boolean = false,
) => {
  const { data } = await gatewayApi.post("/register", {
    email,
    password,
    consent_data_processing: consentDataProcessing,
    consent_marketing: consentMarketing,
  });
  return data;
};

export const verifyEmail = async (email: string, token: string) => {
  const { data } = await gatewayApi.post("/auth/verify-email", { email, token });
  return data;
};

export const resendVerification = async (email: string) => {
  const { data } = await gatewayApi.post("/auth/resend-verification", { email });
  return data;
};

export const forgotPassword = async (email: string) => {
  const { data } = await gatewayApi.post("/auth/forgot-password", { email });
  return data;
};

export const resetPassword = async (
  email: string,
  token: string,
  newPassword: string,
) => {
  const { data } = await gatewayApi.post("/auth/reset-password", {
    email,
    token,
    new_password: newPassword,
  });
  return data;
};

export const userOnboarding = async (
  first_name: string,
  last_name: string,
  customer_name: string,
  user_id: string | null
) => {

    const { data } = await gatewayApi.patch(`/users/${user_id}/`, {
    first_name: first_name,
    last_name: last_name,
    new_customer_name: customer_name
  });
  return data;
}

export const logoutSession = async () => {
  const { data } = await gatewayApi.post("/auth/logout", {});
  return data;
};

export const changePassword = async (
  currentPassword: string,
  newPassword: string,
) => {
  const { data } = await gatewayApi.post("/auth/change-password", {
    current_password: currentPassword,
    new_password: newPassword,
  });
  return data;
};

export interface SessionSummary {
  id: string;
  issued_at: string;
  expires_at: string;
  current: boolean;
}

export const listSessions = async (): Promise<SessionSummary[]> => {
  const { data } = await gatewayApi.get("/auth/sessions");
  return data;
};

export const revokeSession = async (sessionId: string) => {
  const { data } = await gatewayApi.delete(`/auth/sessions/${sessionId}`);
  return data;
};

export interface ConsentState {
  data_processing_granted: boolean;
  data_processing_at: string | null;
  marketing_granted: boolean;
  marketing_at: string | null;
}

export const getConsent = async (): Promise<ConsentState> => {
  const { data } = await gatewayApi.get("/users/me/consent");
  return data;
};

export const updateMarketingConsent = async (
  marketing: boolean,
): Promise<ConsentState> => {
  const { data } = await gatewayApi.patch("/users/me/consent", { marketing });
  return data;
};

export const exportMyData = async () => {
  const { data } = await gatewayApi.get("/users/me/export");
  return data;
};

export const deleteMyAccount = async (userId: string) => {
  const { data } = await gatewayApi.delete(`/users/${userId}`);
  return data;
};

export const requestEmailChange = async (newEmail: string) => {
  const { data } = await gatewayApi.post("/users/me/email", {
    new_email: newEmail,
  });
  return data;
};

export interface UserProfile {
  id: string;
  first_name?: string | null;
  last_name?: string | null;
  email: string;
}

// Own profile via the existing GET /users/{id} (self-access is allowed).
export const getUserProfile = async (userId: string): Promise<UserProfile> => {
  const { data } = await gatewayApi.get(`/users/${userId}`);
  return data;
};
