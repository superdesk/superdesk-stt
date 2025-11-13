#
#    What should be excluded based on content profile
#
#    - Helpers functions
#    - Data definitions
#
#

STT_EXCLUDE_METADATA_LIST = [
    {
        "profile": "viiva",
        "excludeData": [
            {"scheme": "sttnewsroomnote"},
            {"scheme": "sttsmscategory"},
            {"scheme": "stttopstory"},
            {
                "removeKeys": [
                    "byline",
                    "ednote",
                    "sttpublicednote",
                    "sttsubheadline",
                    "extra>sttsubheadline",
                    "extra>sttpublicednote",
                    "body_html",
                ]
            },
        ],
    },
    {
        "profile": "sms",
        "excludeData": [
            {"scheme": "sttnewsroomnote"},
            {"scheme": "stttopstory"},
            {"scheme": "sttsource"},
            {"scheme": "topics"},
            {
                "removeKeys": [
                    "byline",
                    "ednote",
                    "slugline",
                    "headline",
                    "dateline",
                    "source",
                    "anpa_category",
                    "genre",
                    "sttpublicednote",
                    "sttsubheadline",
                    "extra>sttsubheadline",
                    "extra>sttpublicednote",
                    "body_html",
                ]
            },
        ],
    },
    {
        "profile": "pika",
        "excludeData": [
            {"scheme": "stttopstory"},
            {"scheme": "sttsmscategory"},
            {"removeKeys": ["byline", "sttsubheadline", "extra>sttsubheadline"]},
        ],
    },
    {
        "profile": "pikaplus",
        "excludeData": [
            {"scheme": "stttopstory"},
            {"scheme": "sttsmscategory"},
        ],
    },
    {
        "profile": "nettiuutinen",
        "excludeData": [
            {"scheme": "sttsmscategory"},
            {"scheme": "sttnewsroomnote"},
            {"removeKeys": ["ednote"]},
        ],
    },
]


def cleanDict(data, key=None, qcode=None, scheme=None, removeKeys=None):

    if removeKeys is None:
        removeKeys = []

    if isinstance(data, list):

        newList = []
        for index, item in enumerate(data):

            # Is list item dict?
            if isinstance(item, dict):

                cleanedItem = cleanDict(item, key, qcode, scheme, removeKeys)

                # Check for if it is to be removed
                if (
                    (key is not None and key in cleanedItem)
                    or (qcode is not None and cleanedItem.get("qcode", None) == qcode)
                    or (
                        scheme is not None and cleanedItem.get("scheme", None) == scheme
                    )
                ):
                    continue

                newList.append(cleanedItem)
            else:
                newList.append(item)

        return newList

    elif isinstance(data, dict):

        # Create new dictionary
        new_dict = {}

        # Loop through dictionary
        for k, v in data.items():

            # Skip key if it is listed in removeKeys
            if k in removeKeys:
                continue

            new_dict[k] = cleanDict(v, k, qcode, scheme, removeKeys)

        return new_dict

    else:

        # If data is not dict or list return it as is
        return data


def removeMetadata(article):

    currentProfile = None
    cleanedArticle = article

    # Loop through exclude list
    for value in STT_EXCLUDE_METADATA_LIST:

        # For entry (profile definitions)
        for key, value in value.items():

            match key:

                # If profile is set change the currentProfile value to it
                case "profile":
                    currentProfile = value

                # If list of unwanted metadata is defined remove them from the article dictionary
                case "excludeData":

                    articleProfile = article.get("profile", None)

                    # If profiles match we can proceed
                    if articleProfile and currentProfile == articleProfile:

                        for dict in value:

                            # Build params list dynamically
                            params = {
                                "qcode": dict.get("qcode", ""),
                                "scheme": dict.get("scheme", ""),
                                "removeKeys": dict.get("removeKeys", ""),
                            }

                            cleanedArticle = cleanDict(cleanedArticle, **params)

    return cleanedArticle
