"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { isApiError } from "@/lib/api/errors";
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
      <h1 className="text-xl font-semibold">Create your organization</h1>
      <p className="mt-1 text-sm text-zinc-500">
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
        />
        <Input
          label="Email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
        <Input
          label="Password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          minLength={12}
          maxLength={128}
        />
        {register.isError && (
          <p className="text-sm text-red-600">
            {isApiError(register.error) &&
            register.error.code === "registration_conflict"
              ? "Registration failed. Check your details and try again."
              : "Registration failed."}
          </p>
        )}
        <Button type="submit" disabled={register.isPending} className="w-full">
          {register.isPending ? "Creating…" : "Create account"}
        </Button>
      </form>
      <p className="mt-4 text-center text-sm text-zinc-500">
        Already have an account?{" "}
        <Link href="/login" className="text-emerald-600 hover:underline">
          Sign in
        </Link>
      </p>
    </Card>
  );
}
