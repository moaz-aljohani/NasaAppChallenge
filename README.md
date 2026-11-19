# ECORA | NASA Space Apps Challenge 2026

On November 14th and 15th, 2026, we participated in the NASA Space Apps Challenge 2026.

Our team name was **Hasad (حصاد)**, and we had a great idea about improving agriculture in Madinah, Saudi Arabia, by discovering new crops that could grow well in our local environment.

## The Idea

As we know, Madinah is famous for growing dates, but we wanted to explore what other crops could be grown here based on actual environmental data.

So, we came up with **ECORA (إيكورا)**, a project that helps farmers discover suitable crops, find the best time to plant them, and make better use of their agricultural land throughout the year.

## What Did We Do?

We collected real climate data from NASA POWER for Madinah from 2020 to 2025, including temperature, rainfall, humidity, solar radiation, and other environmental parameters.

We also collected soil data from SoilGrids and used the FAO ECOCROP database, which contains information about 2,568 different plant species and their growing requirements.

Then, using Python and an adapted version of the OpenCLIM ECOCROP model, we compared the requirements of each crop with the actual climate and soil conditions in Madinah.

The goal was to find which crops could grow well here and determine the best season to plant them.

## Our Results

After analyzing 2,026 plant species, we found 372 plants with positive suitability scores.

Some of the most interesting results were:

| Crop | Suitability Score |
|---|---:|
| Chickpeas | 100% |
| Quinoa | 93.33% |
| Guar | 80% |

These results were really interesting to us, especially quinoa and guar, as they could be promising alternatives for diversifying agriculture in Madinah.

Of course, these scores are preliminary estimates based on environmental conditions, and real-world farming experiments are still needed.

## Tools and Data

- Python
- Google Colab
- Pandas and NumPy
- [NASA POWER](https://power.larc.nasa.gov/)
- [FAO ECOCROP](https://ecocrop.apps.fao.org/)
- [ISRIC SoilGrids](https://soilgrids.org/)
- [OpenCLIM ECOCROP](https://github.com/OpenCLIM/ecocrop)

We also used LLM to assist us with coding, debugging, and documentation.

## What's Next?

We would love to take this project further by adding more environmental factors, improving water requirement calculations, and testing our recommendations with local farmers.

Our ultimate goal is to help farmers make better decisions, diversify their crops, and contribute to more sustainable agriculture in Saudi Arabia.

## Final Thoughts

Despite the limited time we had during the hackathon, we are really happy with what we achieved as a team. It was a great experience working with real NASA data, learning new things, and building something that could potentially make a difference in our community.

**Team Hasad | فريق حصاد**
