#!/usr/bin/env bash

set -e

EXPORT_DIR=${HOME}/EXPORT
NIGHTLY_KIWIX_ARCHIVES_DIR=${EXPORT_DIR}/NIGHTLY_KIWIX_ARCHIVES/${NIGHTLY_DATE}
NIGHTLY_ZIM_ARCHIVES_DIR=${EXPORT_DIR}/NIGHTLY_ZIM_ARCHIVES/${NIGHTLY_DATE}
RELEASE_KIWIX_ARCHIVES_DIR=${EXPORT_DIR}/RELEASE_KIWIX_ARCHIVES
RELEASE_ZIM_ARCHIVES_DIR=${EXPORT_DIR}/RELEASE_ZIM_ARCHIVES
DIST_KIWIX_ARCHIVES_DIR=${EXPORT_DIR}/DIST_KIWIX_ARCHIVES
DIST_ZIM_ARCHIVES_DIR=${EXPORT_DIR}/DIST_ZIM_ARCHIVES
BINTRAY_ARCHIVES_DIR=${EXPORT_DIR}/BINTRAY_ARCHIVES

if [[ "$TRAVIS_EVENT_TYPE" = "cron" ]]
then
  echo "Publishing nightlies"
  ls ${NIGHTLY_KIWIX_ARCHIVES_DIR}
  scp -rp -i ${SSH_KEY} -o StrictHostKeyChecking=no \
    ${NIGHTLY_KIWIX_ARCHIVES_DIR} \
    ci@download.kiwix.org:/data/download/nightly
  ls ${NIGHTLY_ZIM_ARCHIVES_DIR}
  scp -rp -i ${SSH_KEY} -o StrictHostKeyChecking=no \
    ${NIGHTLY_ZIM_ARCHIVES_DIR} \
    ci@download.openzim.org:/data/openzim/nightly

elif [[ "x$TRAVIS_TAG" != "x" ]]
then
  RELEASE_ARCHIVES=$(find $RELEASE_KIWIX_ARCHIVES_DIR -type f)
  if [[ "x$RELEASE_ARCHIVES" != "x" ]]
  then
    echo "Publishing kiwix archives $RELEASE_ARCHIVES"
    for archive in $RELEASE_ARCHIVES
    do
      subdir=$(basename $(dirname $archive))
      scp -rp -i ${SSH_KEY} -o StrictHostKeyChecking=no \
        ${archive} \
        ci@download.kiwix.org:/data/download/release/${subdir}
    done
  fi

  RELEASE_ARCHIVES=$(find $RELEASE_ZIM_ARCHIVES_DIR -type f)
  if [[ "x$RELEASE_ARCHIVES" != "x" ]]
  then
    echo "Publishing zim archives $RELEASE_ARCHIVES"
    for archive in $RELEASE_ARCHIVES
    do
      subdir=$(basename $(dirname $archive))
      scp -rp -i ${SSH_KEY} -o StrictHostKeyChecking=no \
        ${archive} \
        ci@download.openzim.org:/data/openzim/release/${subdir}
    done
  fi

  DIST_KIWIX_ARCHIVES=$(find $DIST_KIWIX_ARCHIVES_DIR -type f)
  if [[ "x$DIST_KIWIX_ARCHIVES" != "x" ]]
  then
    echo "Publishing dist kiwix archives $DIST_KIWIX_ARCHIVES"
    for archive in $DIST_KIWIX_ARCHIVES
    do
      subdir=$(basename $(dirname $archive))
      scp -rp -i ${SSH_KEY} -o StrictHostKeyChecking=no \
        ${archive} \
        ci@download.kiwix.org:/data/download/release/${subdir}
    done
  fi

  DIST_ZIM_ARCHIVES=$(find $DIST_ZIM_ARCHIVES_DIR -type f)
  if [[ "x$DIST_ZIM_ARCHIVES" != "x" ]]
  then
    echo "Publishing dist zim archives $DIST_ZIM_ARCHIVES"
    for archive in $DIST_ZIM_ARCHIVES
    do
      subdir=$(basename $(dirname $archive))
      scp -rp -i ${SSH_KEY} -o StrictHostKeyChecking=no \
        ${archive} \
        ci@download.openzim.org:/data/openzim/release/${subdir}
    done
  fi

  (cd ${EXPORT_DIR}/GIT
  GIT_REPOS=$(ls -l | awk '/^d/ { print $9 }')
  if [[ "x$GIT_REPOS" != "x" ]]
  then
    echo "Pushing repositories $GIT_REPOS"
    for repo in $GIT_REPOS
    do
      (cd $repo;
      GIT_SSH_COMMAND="ssh -o StrictHostKeyChecking=no -i $SSH_KEY" git push
      )
    done
  fi
  )

  ls $BINTRAY_ARCHIVES_DIR
  BINTRAY_ARCHIVES=$(find $BINTRAY_ARCHIVES_DIR -name "*_bintray_info.json" -type f)
  if [[ "x$BINTRAY_ARCHIVES" != "x" ]]
  then
    echo "Publish bintray $BINTRAY_ARCHIVES"
    for archive_info in $BINTRAY_ARCHIVES
    do
      ${TRAVIS_BUILD_DIR}/scripts/upload_kiwix_lib_android_to_bintray.py $archive_info
    done
 fi

fi

