import { expect, request as pwRequest, type APIRequestContext } from "@playwright/test";
import { jwtDecode } from "jwt-decode";

// Register -> verify -> onboard -> login, returning a context whose token carries a customer_id.
export async function onboardedApiContext(
  request: APIRequestContext,
  baseURL: string | undefined,
): Promise<APIRequestContext> {
  const unique = crypto.randomUUID();
  const email = `e2e-${unique}@example.com`;
  const password = "Passw0rd!23";

  const registerRes = await request.post("/api/v1/register", {
    data: {
      email,
      password,
      first_name: "E2E",
      last_name: "Tester",
      consent_data_processing: true,
    },
  });
  expect(registerRes.status()).toBe(200);

  const resendRes = await request.post("/api/v1/auth/resend-verification", {
    data: { email },
  });
  expect(resendRes.status()).toBe(200);
  const { debug_token: debugToken } = await resendRes.json();

  const verifyRes = await request.post("/api/v1/auth/verify-email", {
    data: { email, token: debugToken },
  });
  expect(verifyRes.status()).toBe(200);
  const { access_token: verifyToken } = await verifyRes.json();
  const userId = jwtDecode<{ user_id: string }>(verifyToken).user_id;

  const registerContext = await pwRequest.newContext({
    baseURL,
    extraHTTPHeaders: { Authorization: `Bearer ${verifyToken}` },
  });
  const onboardRes = await registerContext.patch(`/api/v1/users/${userId}/`, {
    data: { new_customer_name: `E2E Org ${unique}` },
  });
  expect(onboardRes.status()).toBe(200);
  await registerContext.dispose();

  const loginRes = await request.post("/api/v1/auth/login", { data: { email, password } });
  expect(loginRes.status()).toBe(200);
  const { access_token: accessToken } = await loginRes.json();

  return pwRequest.newContext({
    baseURL,
    extraHTTPHeaders: { Authorization: `Bearer ${accessToken}` },
  });
}
