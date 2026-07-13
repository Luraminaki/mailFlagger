#!/usr/bin/env python3
"""Split a suggested blacklist across two providers with different per-provider caps.

Some mail providers cap how many *domains* you can block much more tightly than how many
individual *addresses* you can block (e.g. Yahoo: a handful of domains vs. up to 1000
addresses), while another provider you also use might allow a much larger combined pool (e.g.
Outlook). This implements a simple strategy: give the tight-cap provider's scarce domain slots
to the highest-value repeat offenders, use its address slots for senders worth remembering
individually (freemail addresses, and addresses on domains that didn't make the domain cut but
still repeated), and dump everything - including the full domain list again, as a backstop - on
the generous-cap provider.
"""

from dataclasses import dataclass, field

from mailflagger.analyzer import AnalysisResult, root_domain
from mailflagger.scoring import DomainScore


@dataclass
class SplitResult:
    """Domains/addresses split between a tight-cap and a generous-cap provider.

    Attributes:
        tight_domains (list[DomainScore]): Highest-value domains, capped to fit the tight
            provider's domain limit.
        tight_addresses (list[str]): Addresses worth a tight-provider address ban: those on
            excluded (e.g. freemail) domains, plus those on repeat domains that didn't make
            `tight_domains`, capped to fit the tight provider's address limit.
        generous_domains (list[DomainScore]): The full suggested domain blacklist, uncapped.
        generous_addresses (list[str]): Everything else: one-off addresses, plus any
            `tight_addresses` overflow beyond the tight provider's address cap.
    """
    tight_domains: list[DomainScore] = field(default_factory=list)
    tight_addresses: list[str] = field(default_factory=list)
    generous_domains: list[DomainScore] = field(default_factory=list)
    generous_addresses: list[str] = field(default_factory=list)


def split_for_caps(result: AnalysisResult, all_domain_candidates: list[DomainScore],
                    exclude_domains: frozenset, tight_domain_cap: int, tight_address_cap: int
                    ) -> SplitResult:
    """Splits a suggested blacklist between a tight-cap and a generous-cap provider.

    Args:
        result (AnalysisResult): Parsed addresses (see `mailflagger.analyzer.analyze`).
        all_domain_candidates (list[DomainScore]): The full suggested blacklist (see
            `mailflagger.blacklist.suggest_blacklist`), sorted most-suggested first.
        exclude_domains (frozenset): Domains that can never get a domain ban (e.g. major
            freemail providers) - their addresses go through `tight_addresses` instead.
        tight_domain_cap (int): Max domains the tight-cap provider allows.
        tight_address_cap (int): Max addresses the tight-cap provider allows.

    Returns:
        SplitResult: The four buckets to write out.
    """
    tight_domains = all_domain_candidates[:tight_domain_cap]
    tight_domain_names = {score.domain for score in tight_domains}
    other_domain_names = {score.domain for score in all_domain_candidates[tight_domain_cap:]}

    tight_addresses = []
    generous_addresses = []
    for parsed in result.parsed:
        registrable = root_domain(parsed.domain)
        if registrable in tight_domain_names:
            continue
        address = f'{parsed.local}@{parsed.domain}'
        if registrable in exclude_domains or registrable in other_domain_names:
            tight_addresses.append(address)
        else:
            generous_addresses.append(address)

    tight_addresses = sorted(set(tight_addresses))
    if len(tight_addresses) > tight_address_cap:
        overflow = tight_addresses[tight_address_cap:]
        tight_addresses = tight_addresses[:tight_address_cap]
        generous_addresses.extend(overflow)

    return SplitResult(
        tight_domains=tight_domains,
        tight_addresses=tight_addresses,
        generous_domains=all_domain_candidates,
        generous_addresses=sorted(set(generous_addresses)),
    )
