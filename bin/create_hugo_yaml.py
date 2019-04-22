#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright 2019 Marcel Bollmann <marcel@bollmann.me>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Usage: create_hugo_yaml.py [--importdir=DIR] [--exportdir=DIR] [--debug] [--dry-run]

Creates YAML files containing all necessary Anthology data for the static website generator.

Options:
  --importdir=DIR          Directory to import XML files from. [default: {scriptdir}/../data/]
  --exportdir=DIR          Directory to write YAML files to.   [default: {scriptdir}/../hugo/data/]
  --debug                  Output debug-level log messages.
  -n, --dry-run            Do not write YAML files (useful for debugging).
  -h, --help               Display this helpful text.
"""

from docopt import docopt
from collections import defaultdict
from tqdm import tqdm
import logging as log
import os
import ruamel.yaml

yaml = ruamel.yaml.YAML()
yaml.version = "1.1"

from anthology import Anthology
from anthology.utils import SeverityTracker


def export_anthology(anthology, outdir, dryrun=False):
    # Create directories
    for subdir in ("", "papers", "people"):
        target_dir = "{}/{}".format(outdir, subdir)
        if not os.path.isdir(target_dir):
            os.mkdir(target_dir)

    # Prepare paper index
    papers = defaultdict(dict)
    for id_, paper in anthology.papers.items():
        log.debug("export_anthology: processing paper '{}'".format(id_))
        data = paper.as_dict()
        data["title_html"] = paper.get_title("html")
        del data["xml_title"]
        if "xml_booktitle" in data:
            data["booktitle_html"] = paper.get_booktitle("html")
            del data["xml_booktitle"]
        if "xml_abstract" in data:
            data["abstract_html"] = paper.get_abstract("html")
            del data["xml_abstract"]
        if "author" in data:
            data["author"] = [
                anthology.people.get_slug(name) for name in data["author"]
            ]
        if "editor" in data:
            data["editor"] = [
                anthology.people.get_slug(name) for name in data["editor"]
            ]
        papers[paper.top_level_id][paper.full_id] = data

    # Prepare people index
    people = defaultdict(dict)
    for name in anthology.people.names():
        log.debug("export_anthology: processing person '{}'".format(repr(name)))
        data = name.as_dict()
        slug = anthology.people.get_slug(name)
        data["slug"] = slug
        if anthology.people.is_canonical(name):
            data["papers"] = sorted(
                anthology.people.get_papers(name, include_variants=True),
                key=lambda p: anthology.papers.get(p).get("year"),
                reverse=True,
            )
            data["coauthors"] = sorted(
                [
                    [anthology.people.get_slug(co_name), count]
                    for (co_name, count) in anthology.people.get_coauthors(
                        name, include_variants=True
                    )
                ],
                key=lambda p: p[1],
                reverse=True,
            )
            data["venues"] = sorted(
                [
                    [venue, count]
                    for (venue, count) in anthology.people.get_venues(
                        anthology.venues, name, include_variants=True
                    ).items()
                ],
                key=lambda p: p[1],
                reverse=True,
            )
            if anthology.people.has_variants(name):
                data["variant_entries"] = [
                    anthology.people.get_slug(var)
                    for var in anthology.people.get_registered_variants(name)
                ]
        else:
            data["canonical_entry"] = anthology.people.get_slug(
                anthology.people.get_canonical_variant(name)
            )
        people[slug[0]][slug] = data

    # Prepare volume index
    volumes = {}
    for id_, volume in anthology.volumes.items():
        log.debug("export_anthology: processing volume '{}'".format(id_))
        data = volume.attrib
        data["title_html"] = volume.get_title("html")
        del data["xml_title"]
        if "xml_abstract" in data:
            del data["xml_abstract"]
        data["papers"] = volume.paper_ids
        if "author" in data:
            data["author"] = [
                anthology.people.get_slug(name) for name in data["author"]
            ]
        if "editor" in data:
            data["editor"] = [
                anthology.people.get_slug(name) for name in data["editor"]
            ]
        volumes[volume.full_id] = data

    # Prepare venue index
    venues = {}
    for acronym, data in anthology.venues.items():
        data = data.copy()
        data["volumes_by_year"] = {
            year: sorted(filter(lambda k: volumes[k]["year"] == year, data["volumes"]))
            for year in sorted(data["years"])
        }
        data["years"] = sorted(list(data["years"]))
        del data["volumes"]
        venues[acronym] = data

    # Prepare SIG index
    sigs = {}
    for acronym, sig in anthology.sigs.items():
        data = {
            "name": sig.name,
            "slug": sig.slug,
            "url": sig.url,
            "volumes_by_year": sig.volumes_by_year,
            "years": sorted([str(year) for year in sig.years]),
        }
        sigs[acronym] = data

    # Dump all
    if not dryrun:
        progress = tqdm(total=len(papers) + len(people) + 7)
        for top_level_id, paper_list in papers.items():
            with open("{}/papers/{}.yaml".format(outdir, top_level_id), "w") as f:
                yaml.dump(paper_list, stream=f)
            progress.update()

        with open("{}/volumes.yaml".format(outdir), "w") as f:
            yaml.dump(volumes, stream=f)
        progress.update(5)

        with open("{}/venues.yaml".format(outdir), "w") as f:
            yaml.dump(venues, stream=f)
        progress.update()

        with open("{}/sigs.yaml".format(outdir), "w") as f:
            yaml.dump(sigs, stream=f)
        progress.update()

        for first_letter, people_list in people.items():
            with open("{}/people/{}.yaml".format(outdir, first_letter), "w") as f:
                yaml.dump(people_list, stream=f)
            progress.update()
        progress.close()


if __name__ == "__main__":
    args = docopt(__doc__)
    scriptdir = os.path.dirname(os.path.abspath(__file__))
    if "{scriptdir}" in args["--importdir"]:
        args["--importdir"] = os.path.abspath(
            args["--importdir"].format(scriptdir=scriptdir)
        )
    if "{scriptdir}" in args["--exportdir"]:
        args["--exportdir"] = os.path.abspath(
            args["--exportdir"].format(scriptdir=scriptdir)
        )

    log_level = log.DEBUG if args["--debug"] else log.INFO
    log.basicConfig(format="%(levelname)-8s %(message)s", level=log_level)
    tracker = SeverityTracker()
    log.getLogger().addHandler(tracker)

    log.info("Reading the Anthology data...")
    anthology = Anthology(importdir=args["--importdir"])
    log.info("Exporting to YAML...")
    export_anthology(anthology, args["--exportdir"], dryrun=args["--dry-run"])

    if tracker.highest >= log.ERROR:
        exit(1)
