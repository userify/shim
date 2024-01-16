# Security Policy

## Support

Userify supports and automatically distributes the latest shim version. Please test only with the latest shim version.

## Scope of Vulnerabilities

We are interested in any vulnerabilities that might result in exposure of Userify or customer systems. There are a few classes of issues that we do not consider bounty-able vulnerabilities, including but not limited to:

  * "self-pwn" like self-XSS
  * semi-public user info such as email, username, public key, etc that is already within that user's Userify organization or company
  * similar semi-public information such as username, public key, etc that is already properly available to an instance/server in a server group
  * email spoofing, since this is a limitation of email protocols (unfortunately DKIM does not fully resolve this)
  * DNS spoofing / MITM, since DANE does not fully resolve this (but TLS helps)
  * limitations in TLS such as CA pwnage, cipher choices, etc.
  * theoretical exploits
  * actual exploits from factors outside of our control, such as TLS root key leakage

However, obviously we would be exceedingly grateful if you become aware of any vulnerabilities (for example with our CDN provider). :)

## Userify's security stance

We deliberately keep our dependencies to an absolute minimum and choose more secure, interpreted languages. We carefully evaluate packages and repositories to help protect against supply chain attacks, and choose modern hash and cipher suites that are considered best practice, such as X25519, bcrypt, argon2ID, etc.

Although there are absolutely brilliant programmers everywhere, all of our core product code is written in the United States, and we carefully review every single line of code that goes into Userify.

We'd rather be boring and old than young and exciting ;)

## Historical vulnerabilities

All of this boringness means we've been blessed with exceedingly few security incidents and all were resolved quickly, within hours. In the past we've paid bounties for found vulnerabilities like this:

  * an XSS on a temporary 404 page (not exploitable because Userify doesn't use cookies or stateful logins; you have to log in each time). We still paid the bug bounty even though it was out of scope.
  * demoted but still authorized users were not fully demoted (this only applied if the user was still part of the company) (in scope, bounty paid)
  * missing X-Frame-Options headers (out of scope, but we still paid a bounty)

We also get a fair number of out of scope bug reports. Please carefully review the scope above to save us both time before submitting a bug report.

## Reporting a Vulnerability

Please email security or support at our website in order to report a security vulnerability.

If we accept a vulnerability, our support will respond as soon as possible. If we confirm the vulnerability, even if minor, we will offer a bug bounty (typically $100 or $500) via PayPal. Even if it's out of scope but shows creativity or something like that, we'll try to make it worth your time.

Thank you very much to the entire security community -- white hats, gray hats, we love y'all!
