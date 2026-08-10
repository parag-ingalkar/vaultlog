"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { isApiError } from "@/lib/api/errors";
import { fieldErrorsFromApi } from "@/lib/form-errors";
import { useRegisterMutation } from "@/domains/auth/mutations";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";

export default function RegisterPage() {
  const router = useRouter();
  const register = useRegisterMutation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [organizationName, setOrganizationName] = useState("");

  const fieldErrors = isApiError(register.error)
    ? fieldErrorsFromApi(register.error.fields)
    : {};

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await register.mutateAsync({
        email,
        password,
        organization_name: organizationName,
      });
      router.replace("/login?registered=1");
    } catch {
      // shown below
    }
  };

  return (
    <Card>
      <h1 className="text-xl font-semibold text-ink">Create your organization</h1>
      <p className="mt-1 text-sm text-muted">
        Register as the founding owner. You&apos;ll sign in separately after
        registration.
      </p>
      <form onSubmit={handleSubmit} className="mt-6 space-y-4">
        <Input
          label="Organization name"
          value={organizationName}
          onChange={(e) => setOrganizationName(e.target.value)}
          required
          minLength={1}
          maxLength={200}
          error={fieldErrors.organization_name}
        />
        <Input
          label="Email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          error={fieldErrors.email}
        />
        <Input
          label="Password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          minLength={12}
          maxLength={128}
          hint="At least 12 characters"
          error={fieldErrors.password}
        />
        {register.isError && !Object.keys(fieldErrors).length && (
          <p className="text-sm text-danger" role="alert">
            {isApiError(register.error) &&
            register.error.code === "registration_conflict"
              ? "Registration failed. Check your details and try again."
              : "Registration failed."}
          </p>
        )}
        <Button type="submit" loading={register.isPending} className="w-full">
          Create account
        </Button>
      </form>
      <p className="mt-6 text-center text-sm text-muted">
        Already have an account?{" "}
        <Link href="/login" className="font-medium text-primary hover:underline">
          Sign in
        </Link>
      </p>
    </Card>
  );
}
