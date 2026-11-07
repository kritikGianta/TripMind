import { z } from "zod";

/** Client-side rules mirror the API's (8–128 character passwords, NIST SP 800-63B: no composition rules). */
export const signInSchema = z.object({
  email: z.email("Enter a valid email address."),
  password: z.string().min(1, "Enter your password."),
});

export const signUpSchema = z.object({
  full_name: z.string().trim().min(1, "Enter your name.").max(120, "Use 120 characters or fewer."),
  email: z.email("Enter a valid email address."),
  password: z
    .string()
    .min(8, "Use at least 8 characters.")
    .max(128, "Use 128 characters or fewer."),
});

export type SignInValues = z.infer<typeof signInSchema>;
export type SignUpValues = z.infer<typeof signUpSchema>;
